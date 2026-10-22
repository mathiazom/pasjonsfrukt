import asyncio
import contextlib
import re
from pathlib import Path

from podme_api import (
    PodMeDefaultAuthClient,
    PodMeUserCredentials,
    PodMeClient,
    PodMeEpisode,
)
from podme_api.models import PodMeDownloadProgressTask
from podme_api.const import PodMeRegion
from podme_api.models import PodMeLanguage
from rfeed import Item, Guid, Enclosure, Feed, Image, iTunesItem, iTunes

from .config import ApiConfig, Config

# Number of HLS media segments to download concurrently
HLS_CONCURRENCY = 8


@contextlib.asynccontextmanager
async def get_podme_client(email: str, password: str, api_config: ApiConfig = None):
    api_config = api_config or ApiConfig()
    auth_client = PodMeDefaultAuthClient(
        user_credentials=PodMeUserCredentials(email=email, password=password),
    )
    client = PodMeClient(
        auth_client=auth_client,
        request_timeout=api_config.request_timeout,
        disable_credentials_storage=api_config.disable_credentials_storage,
    )
    if api_config.region is not None:
        auth_client.region = PodMeRegion[api_config.region.upper()]
    client.region = auth_client.region
    if api_config.language is not None:
        client.language = PodMeLanguage[api_config.language.upper()]
    try:
        await client.__aenter__()
        yield client
    finally:
        await client.__aexit__(None, None, None)


def resolve_uri(base_url: str, uri: str) -> str:
    """Resolve a (possibly relative) playlist URI against the playlist URL.

    Uses plain string handling to preserve the exact percent-encoding of
    Akamai tokens (hdntl/hdnts) — URL libraries tend to re-encode them,
    which invalidates the HMAC.

    """
    if uri.startswith("http://") or uri.startswith("https://"):
        return uri
    return base_url.split("?")[0].rsplit("/", 1)[0] + "/" + uri


async def fetch_bytes(client: PodMeClient, url: str) -> bytes:
    async with client.session.get(url) as resp:
        resp.raise_for_status()
        return await resp.read()


async def decrypt_segment(data: bytes, key: bytes, iv: bytes) -> bytes:
    """Decrypt one AES-128-CBC encrypted HLS segment (PKCS7 padding)."""
    proc = await asyncio.create_subprocess_exec(
        "openssl",
        "enc",
        "-d",
        "-aes-128-cbc",
        "-K",
        key.hex(),
        "-iv",
        iv.hex(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate(data)
    if proc.returncode != 0:
        raise RuntimeError("openssl failed to decrypt HLS segment")
    return out


def find_audio_variant(master_content: str) -> str | None:
    """Find the audio-only variant URI in an HLS master playlist.

    Looks for the #EXT-X-STREAM-INF entry without video codecs (no 'avc')
    and returns the URI on the following line.
    """
    lines = master_content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and "avc" not in line:
            for j in range(i + 1, len(lines)):
                candidate = lines[j].strip()
                if candidate and not candidate.startswith("#"):
                    return candidate
    return None


async def harvest_hls_episode(
    client: PodMeClient,
    episode_id: int,
    master_url: str,
    target_path: Path,
):
    """Download the audio track of an HLS (video) episode to an mp3 file.

    PodMe serves some (video) episodes as AES-128 encrypted HLS streams.
    The download URL points to a master playlist. We resolve the audio-only
    variant, download the (encrypted) media segments, decrypt them, and
    remux/transcode them into a single mp3 file with ffmpeg.

    """
    master = (await fetch_bytes(client, master_url)).decode("utf-8")
    audio_uri = find_audio_variant(master)
    if audio_uri is None:
        raise RuntimeError(
            f"no audio-only variant found in HLS master playlist for episode {episode_id}"
        )
    audio_playlist_url = resolve_uri(master_url, audio_uri)

    playlist = (await fetch_bytes(client, audio_playlist_url)).decode("utf-8")

    init_uri = None
    key_uri = None
    key_iv = None
    media_sequence = 0
    segments = []
    for line in playlist.splitlines():
        if line.startswith("#EXT-X-MAP:"):
            init_uri = line.split('URI="')[1].split('"')[0]
        elif line.startswith("#EXT-X-KEY:"):
            key_uri = line.split('URI="')[1].split('"')[0]
            iv_match = re.search(r"IV=0[xX]([0-9a-fA-F]+)", line)
            if iv_match:
                key_iv = bytes.fromhex(iv_match.group(1).zfill(32))
        elif line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            media_sequence = int(line.split(":", 1)[1])
        elif not line.startswith("#") and line.strip():
            segments.append(line.strip())

    if init_uri is None or key_uri is None or not segments:
        raise RuntimeError(
            f"could not parse HLS audio playlist for episode {episode_id}"
        )

    # fetch encryption key and (unencrypted) init segment
    key = await fetch_bytes(client, resolve_uri(audio_playlist_url, key_uri))
    raw = await fetch_bytes(client, resolve_uri(audio_playlist_url, init_uri))

    # download + decrypt all media segments concurrently
    semaphore = asyncio.Semaphore(HLS_CONCURRENCY)

    async def fetch_segment(index: int, uri: str) -> bytes:
        async with semaphore:
            data = await fetch_bytes(client, resolve_uri(audio_playlist_url, uri))
            iv = (
                key_iv
                if key_iv is not None
                else (media_sequence + index).to_bytes(16, "big")
            )
            return await decrypt_segment(data, key, iv)

    tasks = [fetch_segment(i, uri) for i, uri in enumerate(segments)]
    print(
        f"[INFO] Downloading HLS audio for episode {episode_id}: {len(segments)} segments"
    )
    # gather() preserves the order of `tasks`, unlike as_completed() — the
    # order of media segments in the output file must be strictly sequential
    results = await asyncio.gather(*tasks)
    raw += b"".join(results)
    print(
        f"[INFO] HLS download of episode {episode_id} complete: {len(segments)} segments"
    )

    # concat to a temporary fragmented-mp4, then transcode to mp3
    tmp_fmp4 = target_path.with_suffix(".fmp4")
    tmp_fmp4.write_bytes(raw)
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(tmp_fmp4),
            "-vn",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(target_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed to transcode episode {episode_id}: {stderr.decode()[:500]}"
            )
    finally:
        tmp_fmp4.unlink(missing_ok=True)
    print(f"[INFO] Finished HLS download of episode {episode_id} to {target_path}")


async def harvest_podcast(client: PodMeClient, config: Config, slug: str):
    if slug not in config.podcasts:
        print(f"[FAIL] The slug '{slug}' did not match any podcasts in the config file")
        return
    most_recent_episodes_limit = config.podcasts[slug].most_recent_episodes_limit
    if most_recent_episodes_limit is None:
        episodes = await client.get_episode_list(slug)
    else:
        episodes = await client.get_latest_episodes(slug, most_recent_episodes_limit)

    if len(episodes) == 0:
        print(f"[WARN] Could not find any published episodes for '{slug}'")
        return

    published_ids = [e.id for e in episodes]
    harvested_ids = await harvested_episode_ids(client, config, slug)
    to_harvest = [e for e in published_ids if e not in harvested_ids]
    if len(to_harvest) == 0:
        print(
            f"[INFO] Nothing new from '{slug}', all available episodes already harvested"
            f"{f' (only looking at {most_recent_episodes_limit} most recent)' if most_recent_episodes_limit is not None else ''}"
        )
        return
    print(
        f"[INFO] Found {len(to_harvest)} new episode{'s' if len(to_harvest) > 1 else ''} of '{slug}' ready to harvest"
        f"{f' (only looking at {most_recent_episodes_limit} most recent)' if most_recent_episodes_limit is not None else ''}"
    )
    podcast_dir = build_podcast_dir(config, slug)
    podcast_dir.mkdir(parents=True, exist_ok=True)

    # harvest each missing episode
    download_urls = await client.get_episode_download_url_bulk(to_harvest)

    direct_downloads = []
    hls_downloads = []
    for episode_id, url in download_urls:
        if ".m3u8" in str(url):
            hls_downloads.append((episode_id, str(url)))
        else:
            direct_downloads.append((url, podcast_dir / f"{episode_id}.mp3"))

    def log_progress(_: PodMeDownloadProgressTask, url: str, progress: int, total: int):
        print(f"[INFO] Downloading from {url}: {progress}/{total}.")

    def log_finished(url: str, path: str):
        print(f"[INFO] Finished downloading {url} to {path}.")

    if direct_downloads:
        await client.download_files(
            direct_downloads, on_progress=log_progress, on_finished=log_finished
        )

    for episode_id, url in hls_downloads:
        try:
            await harvest_hls_episode(
                client,
                episode_id,
                url,
                podcast_dir / f"{episode_id}.mp3",
            )
        except Exception as err:
            print(f"[FAIL] HLS download of episode {episode_id} failed: {err}")
            # remove partial file so the episode is retried next harvest
            (podcast_dir / f"{episode_id}.mp3").unlink(missing_ok=True)

    await sync_slug_feed(client, config, slug)


async def harvested_episode_ids(client: PodMeClient, config: Config, slug: str):
    podcast_dir = build_podcast_dir(config, slug)
    if not podcast_dir.is_dir():
        # no directory, so clearly no harvested episodes
        return []
    episode_ids = await client.get_episode_ids(slug)
    harvested = []
    for f in podcast_dir.iterdir():
        if not f.is_file():
            continue
        m = re.match(r"(.*)\.mp3$", f.name)
        if m is not None:
            episode_id = int(m.group(1))
            if episode_id in episode_ids:
                harvested.append(episode_id)
    return harvested


def get_secret_query_parameter(config: Config):
    if config.secret is None:
        return ""  # no secret required, so don't append query parameter
    return f"?secret={config.secret}"


def build_podcast_dir(config: Config, slug: str):
    return Path(config.yield_dir) / slug


def build_podcast_feed_path(config: Config, slug: str):
    return (
        build_podcast_dir(config, slug) / f"{config.podcasts.get(slug).feed_name}.xml"
    )


def build_podcast_episode_file_path(config: Config, podcast_slug: str, episode_id: int):
    return build_podcast_dir(config, podcast_slug) / f"{episode_id}.mp3"


def build_feed(
    config: Config,
    episodes: list[PodMeEpisode],
    slug: str,
    title: str,
    description: str,
    image_url: str,
):
    secret_query_param = get_secret_query_parameter(config)
    items = []
    for e in episodes:
        episode_id = e.id
        episode_path = f"{slug}/{episode_id}"
        items.append(
            Item(
                title=e.title,
                description=e.description,
                guid=Guid(episode_id, isPermaLink=False),
                enclosure=Enclosure(
                    url=f"{config.host}/{episode_path}{secret_query_param}",
                    type="audio/mpeg",
                    length=build_podcast_episode_file_path(config, slug, episode_id)
                    .stat()
                    .st_size,
                ),
                pubDate=e.date_added,
                extensions=[
                    iTunesItem(
                        author=e.author_full_name,
                        duration=e.length,
                    )
                ],
            )
        )
    feed_link = f"{config.host}/{slug}{secret_query_param}"
    feed = Feed(
        title=title,
        link=feed_link,
        description=description,
        language="no",
        image=Image(url=image_url, title=title, link=feed_link),
        items=sorted(items, key=lambda i: i.pubDate, reverse=True),
        extensions=[iTunes(block="Yes")],
    )
    return feed.rss()


async def sync_slug_feed(client: PodMeClient, config: Config, slug: str):
    if slug not in config.podcasts:
        print(f"[FAIL] The slug '{slug}' did not match any podcasts in the config file")
        return
    print(f"[INFO] Syncing '{slug}' feed...")
    episode_ids = await harvested_episode_ids(client, config, slug)
    episodes = await client.get_episodes_info(episode_ids)
    podcast_info = await client.get_podcast_info(slug)
    feed = build_feed(
        config,
        episodes,
        slug,
        podcast_info.title,
        podcast_info.description,
        podcast_info.image_url,
    )
    build_podcast_dir(config, slug).mkdir(parents=True, exist_ok=True)
    with build_podcast_feed_path(config, slug).open("w", encoding="utf-8") as feed_file:
        feed_file.write(feed)
    print(
        f"[INFO] '{slug}' feed now serving {len(episodes)} episode{'s' if len(episodes) != 1 else ''}"
    )
