import os
import re
import sys

from starlette.responses import Response
from rfeed import Item, Guid, Enclosure, Feed, Image, iTunesItem, iTunes
import podme_api
from podme_api.exceptions import AccessDeniedError

from definitions import APP_ROOT
from exceptions import InvalidConfigError
from utils import date_of_episode
from app import conf


class RSSResponse(Response):
    media_type = 'application/xml'
    charset = 'utf-8'


def harvest_all(client):
    for slug in conf.podcasts:
        harvest(client, slug)


def harvest(client, slug):
    if slug not in conf.podcasts:
        print(f"[FAIL] The slug '{slug}' did not match any podcasts in the config file")
        return
    published_ids = client.get_episode_ids(slug)
    if len(published_ids) == 0:
        print(f"[WARN] Could not find any published episodes for '{slug}'")
        return
    harvested_ids = harvested_episode_ids(client, slug)
    to_harvest = [e for e in published_ids if e not in harvested_ids]
    if len(to_harvest) == 0:
        print(f"[INFO] Nothing new from '{slug}', all available episodes already harvested")
        return
    print(
        f"[INFO] Found {len(to_harvest)} new episode{'s' if len(to_harvest) > 1 else ''} of '{slug}' ready to harvest")
    podcast_dir = APP_ROOT / conf.get_podcast_dir(slug)
    os.makedirs(podcast_dir, exist_ok=True)
    # harvest each missing episode
    for episode_id in to_harvest:
        client.download_episode(
            str(podcast_dir / f"{episode_id}.mp3"),  # path must be of type str
            client.get_episode_info(episode_id)['streamUrl']
        )
    sync_feed(client, slug)


def harvested_episodes(client, slug):
    return [client.get_episode_info(e) for e in harvested_episode_ids(client, slug)]


def harvested_episode_ids(client, slug):
    podcast_dir = APP_ROOT / conf.get_podcast_dir(slug)
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


def sync_all_feeds(client):
    for slug in conf.podcasts:
        sync_feed(client, slug)


def sync_feed(client, slug):
    if slug not in conf.podcasts:
        print(f"[FAIL] The slug '{slug}' did not match any podcasts in the config file")
        return
    print(f"[INFO] Syncing '{slug}' feed...")
    episodes = harvested_episodes(client, slug)
    podcast_info = client.get_podcast_info(slug)
    feed = build_feed(
        episodes,
        slug,
        podcast_info['title'],
        podcast_info['description'],
        podcast_info['imageUrl']
    )
    os.makedirs(APP_ROOT / conf.get_podcast_dir(slug), exist_ok=True)
    with open(APP_ROOT / conf.get_podcast_feed_path(slug), "w") as feed_file:
        feed_file.write(feed)
    print(
        f"[INFO] '{slug}' feed now serving {len(episodes)} episode{'s' if len(episodes) != 1 else ''}"
        f" at {conf.host}/{conf.get_podcast_dir(slug)}")


def get_secret_query_parameter():
    if "secret" not in conf or conf.secret is None:
        return ""  # no secret required, so don't append query parameter
    return f"?secret={conf.secret}"


def build_feed(episodes, slug, title, description, image_url):
    items = []
    secret_query_param = get_secret_query_parameter()
    for e in episodes:
        episode_path = f"{conf.get_podcast_dir(slug)}/{e['id']}"
        items.append(Item(
            title=e['title'],
            description=e['description'],
            guid=Guid(e['id'], isPermaLink=False),
            enclosure=Enclosure(
                url=f'{conf.host}/{episode_path}/{secret_query_param}',
                type='audio/mpeg',
                length=(APP_ROOT / f"{episode_path}.mp3").stat().st_size
            ),
            pubDate=date_of_episode(e),
            extensions=[
                iTunesItem(
                    duration=e['length']
                )
            ]
        ))
    feed_link = f"{conf.host}/{conf.get_podcast_dir(slug)}/{secret_query_param}"
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


def main():
    if len(sys.argv) > 1:
        if conf is None:
            raise InvalidConfigError(f"No config defined")
        op = sys.argv[1]
        if op in ["harvest", "sync"]:
            podme_client = podme_api.PodMeClient(
                email=conf.auth.email,
                password=conf.auth.password
            )
            try:
                podme_client.login()
            except AccessDeniedError:
                print("[FAIL] Access denied when retrieving PodMe token, please check your login credentials")
                return
            if len(sys.argv) > 2:
                slug = sys.argv[2]
                if op == "harvest":
                    harvest(podme_client, slug)
                elif op == "sync":
                    sync_feed(podme_client, slug)
            else:
                if op == "harvest":
                    harvest_all(podme_client)
                elif op == "sync":
                    sync_all_feeds(podme_client)
        else:
            print("[FAIL] Argument must be either 'harvest' or 'sync'")
    else:
        print(
            "[FAIL] Missing operation argument. Use 'harvest' to grab new episodes, or 'sync' to update RSS feeds")


if __name__ == '__main__':
    main()
