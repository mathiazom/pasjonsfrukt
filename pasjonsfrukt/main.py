import os
import re

from pathlib import Path
from podme_api import PodMeClient, PodMeSchibstedClient
from podme_api.exceptions import AccessDeniedError
from podme_api.models import PodMeEpisode, PodMePodcast
from rfeed import Item, Guid, Enclosure, Feed, Image, iTunesItem, iTunes, iTunesOwner, iTunesCategory

from .config import Config


def get_podme_client(email: str, password: str, schibsted_client=False):
    if schibsted_client:
        client = PodMeSchibstedClient(
            email=email,
            password=password,
        )
    else:
        client = PodMeClient(
            email=email,
            password=password,
        )
    try:
        client.login()
        return client
    except AccessDeniedError:
        print("[FAIL] Access denied when retrieving PodMe token, please check your login credentials")


def harvest_podcast(client: PodMeClient, config: Config, slug: str):
    if slug not in config.podcasts:
        print(f"[FAIL] The slug '{slug}' did not match any podcasts in the config file")
        return
    published_ids = client.get_episode_ids(slug)
    if len(published_ids) == 0:
        print(f"[WARN] Could not find any published episodes for '{slug}'")
        return
    most_recent_episodes_limit = config.podcasts[slug].most_recent_episodes_limit
    if most_recent_episodes_limit is None:
        relevant_harvest_ids = published_ids
    elif most_recent_episodes_limit <= 0:
        relevant_harvest_ids = []
    else:
        relevant_harvest_ids = published_ids[-most_recent_episodes_limit:]
    harvested_ids = harvested_episode_ids(client, config, slug)
    to_harvest = [e for e in relevant_harvest_ids if e not in harvested_ids]
    if len(to_harvest) == 0:
        print(f"[INFO] Nothing new from '{slug}', all available episodes already harvested"
              f"{f' (only looking at {most_recent_episodes_limit} most recent)' if most_recent_episodes_limit is not None else ''}")
        return
    print(
        f"[INFO] Found {len(to_harvest)} new episode{'s' if len(to_harvest) > 1 else ''} of '{slug}' ready to harvest"
        f"{f' (only looking at {most_recent_episodes_limit} most recent)' if most_recent_episodes_limit is not None else ''}"
    )
    podcast_dir = build_podcast_dir(config, slug)
    os.makedirs(podcast_dir, exist_ok=True)
    # harvest each missing episode
    for episode_id in to_harvest:
        client.download_episode(
            str((podcast_dir / f"{episode_id}.mp3").as_posix()),  # path must be of type str
            client.get_episode_info(episode_id)['streamUrl']
        )
    sync_slug_feed(client, config, slug)


def harvested_episode_ids(client: PodMeClient, config: Config, slug: str):
    podcast_dir = build_podcast_dir(config, slug)
    if not podcast_dir.is_dir():
        # no directory, so clearly no harvested episodes
        return []
    episode_ids = client.get_episode_ids(slug)
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


def sanitize_xml(content: str) -> str:
    return content.encode().decode('unicode-escape')


def build_podcast_dir(config: Config, slug: str):
    return Path(config.yield_dir) / slug


def build_podcast_feed_path(config: Config, slug: str):
    return build_podcast_dir(config, slug) / f"{config.podcasts.get(slug).feed_name}.xml"


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
        items.append(Item(
            title=e.title,
            description=e.description,
            guid=Guid(episode_id, isPermaLink=False),
            enclosure=Enclosure(
                url=f'{config.host}/{episode_path}/{secret_query_param}',
                type='audio/mpeg',
                length=build_podcast_episode_file_path(config, slug, episode_id).stat().st_size
            ),
            pubDate=e.dateAdded,
            extensions=[
                iTunesItem(
                    author=e.authorFullName,
                    duration=e.length,
                )
            ]
        ))
    feed_link = f"{config.host}/{slug}/{secret_query_param}"
    feed = Feed(
        title=podcast.title,
        link=feed_link,
        description=podcast.description,
        language="no",
        image=Image(
            url=podcast.imageUrl,
            title=podcast.title,
            link=feed_link,
        ),
        categories=[c.key for c in podcast.categories],
        copyright="PodMe",
        items=sorted(items, key=lambda i: i.pubDate, reverse=True),
        extensions=[iTunes(
            block='Yes',
            author=podcast.authorFullName,
            subtitle=(podcast.description[:255] + '..') if len(podcast.description) > 255 else podcast.description,
            summary=podcast.description,
            image=podcast.imageUrl,
            explicit="clean",
            owner=iTunesOwner(
                name=podcast.authorFullName,
                email='hej@podme.com',
            ),
            categories=[iTunesCategory(c.key) for c in podcast.categories],
        )]
    )
    return feed.rss()


def sync_slug_feed(client: PodMeClient, config: Config, slug: str):
    if slug not in config.podcasts:
        print(f"[FAIL] The slug '{slug}' did not match any podcasts in the config file")
        return
    print(f"[INFO] Syncing '{slug}' feed...")
    episodes = [client.get_episode_info(e) for e in harvested_episode_ids(client, config, slug)]
    podcast_info = client.get_podcast_info(slug)
    feed = build_feed(
        config,
        episodes,
        slug,
        podcast_info,
    )
    os.makedirs(build_podcast_dir(config, slug), exist_ok=True)
    with open(build_podcast_feed_path(config, slug), mode="w", encoding="utf-8") as feed_file:
        feed_file.write(feed)
    print(f"[INFO] '{slug}' feed now serving {len(episodes)} episode{'s' if len(episodes) != 1 else ''}")
