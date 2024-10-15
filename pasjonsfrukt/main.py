import contextlib
import re
from pathlib import Path

from podme_api import PodMeDefaultAuthClient, PodMeUserCredentials, PodMeClient, PodMeEpisode
from rfeed import Item, Guid, Enclosure, Feed, Image, iTunesItem, iTunes

from .config import Config


@contextlib.asynccontextmanager
async def get_podme_client(email: str, password: str):
    client = PodMeClient(
        auth_client=PodMeDefaultAuthClient(
            user_credentials=PodMeUserCredentials(email=email, password=password)
        ),
        request_timeout=30,
    )
    try:
        await client.__aenter__()
        yield client
    finally:
        await client.__aexit__(None, None, None)


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
        print(f"[INFO] Nothing new from '{slug}', all available episodes already harvested"
              f"{f' (only looking at {most_recent_episodes_limit} most recent)' if most_recent_episodes_limit is not None else ''}")
        return
    print(
        f"[INFO] Found {len(to_harvest)} new episode{'s' if len(to_harvest) > 1 else ''} of '{slug}' ready to harvest"
        f"{f' (only looking at {most_recent_episodes_limit} most recent)' if most_recent_episodes_limit is not None else ''}"
    )
    podcast_dir = build_podcast_dir(config, slug)
    podcast_dir.mkdir(parents=True, exist_ok=True)

    # harvest each missing episode
    download_urls = await client.get_episode_download_url_bulk(to_harvest)
    download_infos = [
        (url, podcast_dir / f"{episode_id}.mp3") for episode_id, url in download_urls
    ]

    def log_progress(url: str, progress: int, total: int):
        print(f"[INFO] Downloading from {url}: {progress}/{total}.")

    def log_finished(url: str, path: str):
        print(f"[INFO] Finished downloading {url} to {path}.")

    await client.download_files(
        download_infos, on_progress=log_progress, on_finished=log_finished
    )

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
        m = re.match(r'(.*)\.mp3$', f.name)
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
    return build_podcast_dir(config, slug) / f"{config.podcasts.get(slug).feed_name}.xml"


def build_podcast_episode_file_path(config: Config, podcast_slug: str, episode_id: int):
    return build_podcast_dir(config, podcast_slug) / f"{episode_id}.mp3"


def build_feed(config: Config, episodes: list[PodMeEpisode], slug: str, title: str, description: str,
               image_url: str):
    secret_query_param = get_secret_query_parameter(config)
    items = []
    for e in episodes:
        episode_id = e.id
        episode_path = f"{slug}/{episode_id}"
        items.append(Item(
            title=e.title,
            description=e.description,
            guid=Guid(episode_id, isPermaLink=False),
            enclosure=Enclosure(
                url=f'{config.host}/{episode_path}{secret_query_param}',
                type='audio/mpeg',
                length=build_podcast_episode_file_path(config, slug, episode_id).stat().st_size
            ),
            pubDate=e.date_added,
            extensions=[
                iTunesItem(
                    author=e.author_full_name,
                    duration=e.length,
                )
            ]
        ))
    feed_link = f"{config.host}/{slug}{secret_query_param}"
    feed = Feed(
        title=title,
        link=feed_link,
        description=description,
        language="no",
        image=Image(
            url=image_url,
            title=title,
            link=feed_link
        ),
        items=sorted(items, key=lambda i: i.pubDate, reverse=True),
        extensions=[iTunes(block='Yes')]
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
        podcast_info.image_url
    )
    build_podcast_dir(config, slug).mkdir(parents=True, exist_ok=True)
    with build_podcast_feed_path(config, slug).open("w", encoding="utf-8") as feed_file:
        feed_file.write(feed)
    print(f"[INFO] '{slug}' feed now serving {len(episodes)} episode{'s' if len(episodes) != 1 else ''}")
