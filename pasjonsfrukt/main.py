import contextlib
import re
import logging
from pathlib import Path

from podme_api import (
    PodMeDefaultAuthClient,
    PodMeUserCredentials,
    PodMeClient,
    PodMeEpisode,
    PodMePodcast,
)
from rfeed import (
    Item,
    Guid,
    Enclosure,
    Feed,
    Image,
    iTunesItem,
    iTunes,
    iTunesCategory,
    iTunesOwner,
)
from jinja2 import Template

from .config import Config

_LOGGER = logging.getLogger(__package__)


@contextlib.asynccontextmanager
async def get_podme_client(email: str, password: str) -> PodMeClient:
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
        _LOGGER.error(
            f"The slug '{slug}' did not match any podcasts in the config file"
        )
        return
    most_recent_episodes_limit = config.podcasts[slug].most_recent_episodes_limit
    if most_recent_episodes_limit is None:
        episodes = await client.get_episode_list(slug)
    else:
        episodes = await client.get_latest_episodes(slug, most_recent_episodes_limit)

    if len(episodes) == 0:
        _LOGGER.warning(f"Could not find any published episodes for '{slug}'")
        return

    published_ids = [e.id for e in episodes]
    harvested_ids = await harvested_episode_ids(client, config, slug)
    to_harvest = [e for e in published_ids if e not in harvested_ids]
    if len(to_harvest) == 0:
        _LOGGER.info(
            f"Nothing new from '{slug}', all available episodes already harvested"
            f" (only looking at {most_recent_episodes_limit} most recent)"
            if most_recent_episodes_limit is not None
            else ""
        )
        return
    _LOGGER.info(
        f"Found {len(to_harvest)} new episode{'s' if len(to_harvest) > 1 else ''} of '{slug}' ready to harvest"
        f" (only looking at {most_recent_episodes_limit} most recent)"
        if most_recent_episodes_limit is not None
        else ""
    )
    podcast_dir = build_podcast_dir(config, slug)
    podcast_dir.mkdir(parents=True, exist_ok=True)

    # harvest each missing episode
    download_urls = await client.get_episode_download_url_bulk(to_harvest)
    download_infos = [
        (url, build_podcast_episode_file_path(config, slug, episode_id))
        for episode_id, url in download_urls
    ]

    def log_progress(url: str, progress: int, total: int):
        percentage = int(100 * progress / total)
        _LOGGER.debug(f"Downloading from {url}: {percentage}%")

    def log_finished(url: str, path: str):
        _LOGGER.info(f"Finished downloading {url} to {path}.")

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
        m = re.match(r"(.*)\.mp3$", f.name)
        if m is not None:
            episode_id = int(m.group(1))
            if episode_id in episode_ids:
                harvested.append(episode_id)
    return harvested


def get_secret_query_parameter(config: Config):
    if config.secret is None:
        return ""  # no secret required, so don't append query parameter
    return f"secret={config.secret}"


def sanitize_xml(content: str) -> str:
    return content.encode().decode("unicode-escape")


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
    podcast: PodMePodcast,
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
                    url=str(
                        config.build_url(episode_path).with_query(secret_query_param)
                    ),
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
    feed_link = str(config.build_url(slug).with_query(secret_query_param))
    feed = Feed(
        title=podcast.title,
        link=feed_link,
        description=podcast.description,
        language="no",
        image=Image(url=podcast.image_url, title=podcast.title, link=feed_link),
        categories=[c.name for c in podcast.categories],
        copyright="PodMe",
        items=sorted(items, key=lambda i: i.pubDate, reverse=True),
        extensions=[
            iTunes(
                block=True,
                author=podcast.author_full_name,
                subtitle=(podcast.description[:255] + "..")
                if len(podcast.description) > 255
                else podcast.description,
                summary=podcast.description,
                image=podcast.image_url,
                explicit=False,
                owner=iTunesOwner(
                    name=podcast.author_full_name,
                    email="hej@podme.com",
                ),
                categories=[iTunesCategory(c.name) for c in podcast.categories],
            )
        ],
    )
    return feed.rss()


async def sync_index(config: Config, podcasts: list[PodMePodcast]):
    _LOGGER.info("Syncing index...")
    templates_dir = Path(config.templates_dir)
    yield_dir = Path(config.yield_dir)

    index_tpl = templates_dir / "index.html.j2"
    with index_tpl.open("r", encoding="utf-8") as f:
        template = Template(f.read())
        html_output = template.render(
            config=config, url=config.build_url(), podcasts=podcasts
        )

    with (yield_dir / "index.html").open("w", encoding="utf-8") as f:
        f.write(html_output)

    _LOGGER.info(f"Index successfully saved to {yield_dir / 'index.html'}")


async def sync_slug_feed(client: PodMeClient, config: Config, slug: str):
    if slug not in config.podcasts:
        _LOGGER.error(
            f"The slug '{slug}' did not match any podcasts in the config file"
        )
        return
    _LOGGER.info(f"Syncing '{slug}' feed...")
    episode_ids = await harvested_episode_ids(client, config, slug)
    episodes = await client.get_episodes_info(episode_ids)
    podcast_info = await client.get_podcast_info(slug)
    feed = build_feed(
        config,
        episodes,
        slug,
        podcast_info,
    )
    build_podcast_dir(config, slug).mkdir(parents=True, exist_ok=True)
    with build_podcast_feed_path(config, slug).open("w", encoding="utf-8") as feed_file:
        feed_file.write(feed)
    _LOGGER.info(
        f"'{slug}' feed now serving {len(episodes)} episode{'s' if len(episodes) != 1 else ''}"
    )
