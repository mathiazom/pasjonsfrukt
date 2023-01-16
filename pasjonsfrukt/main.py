import os
import re
from pathlib import Path

from rfeed import Item, Guid, Enclosure, Feed, Image, iTunesItem, iTunes
import podme_api
import podme_api.types
from podme_api.exceptions import AccessDeniedError

from .config import Config
from .utils import date_of_episode


def get_podme_client(email: str, password: str):
    client = podme_api.PodMeClient(
        email=email,
        password=password
    )
    try:
        client.login()
        return client
    except AccessDeniedError:
        print("[FAIL] Access denied when retrieving PodMe token, please check your login credentials")


def harvest_podcast(client: podme_api.PodMeClient, config: Config, slug: str):
    if slug not in config.podcasts:
        print(f"[FAIL] The slug '{slug}' did not match any podcasts in the config file")
        return
    published_ids = client.get_episode_ids(slug)
    if len(published_ids) == 0:
        print(f"[WARN] Could not find any published episodes for '{slug}'")
        return
    harvested_ids = harvested_episode_ids(client, config, slug)
    to_harvest = [e for e in published_ids if e not in harvested_ids]
    if len(to_harvest) == 0:
        print(f"[INFO] Nothing new from '{slug}', all available episodes already harvested")
        return
    print(
        f"[INFO] Found {len(to_harvest)} new episode{'s' if len(to_harvest) > 1 else ''} of '{slug}' ready to harvest")
    podcast_dir = build_podcast_dir(config, slug)
    os.makedirs(podcast_dir, exist_ok=True)
    # harvest each missing episode
    for episode_id in to_harvest:
        client.download_episode(
            str((podcast_dir / f"{episode_id}.mp3").as_posix()),  # path must be of type str
            client.get_episode_info(episode_id)['streamUrl']
        )
    sync_slug_feed(client, config, slug)


def harvested_episode_ids(client: podme_api.PodMeClient, config: Config, slug: str):
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


def build_feed(config: Config, episodes: list[podme_api.types.PodMeEpisode], slug: str, title: str, description: str,
               image_url: str):
    secret_query_param = get_secret_query_parameter(config)
    items = []
    for e in episodes:
        episode_id = e['id']
        episode_path = f"{slug}/{episode_id}"
        items.append(Item(
            title=e['title'],
            description=e['description'],
            guid=Guid(episode_id, isPermaLink=False),
            enclosure=Enclosure(
                url=f'{config.host}/{episode_path}/{secret_query_param}',
                type='audio/mpeg',
                length=build_podcast_episode_file_path(config, slug, episode_id).stat().st_size
            ),
            pubDate=date_of_episode(e),
            extensions=[
                iTunesItem(
                    duration=e['length']
                )
            ]
        ))
    feed_link = f"{config.host}/{slug}/{secret_query_param}"
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
        extensions=[iTunes()]
    )
    return feed.rss()


def sync_slug_feed(client: podme_api.PodMeClient, config: Config, slug: str):
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
        podcast_info['title'],
        podcast_info['description'],
        podcast_info['imageUrl']
    )
    os.makedirs(build_podcast_dir(config, slug), exist_ok=True)
    with open(build_podcast_feed_path(config, slug), mode="w", encoding="utf-8") as feed_file:
        feed_file.write(feed)
    print(f"[INFO] '{slug}' feed now serving {len(episodes)} episode{'s' if len(episodes) != 1 else ''}")
