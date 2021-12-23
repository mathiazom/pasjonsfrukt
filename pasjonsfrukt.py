import os
import re
import sys

from starlette.responses import Response
from rfeed import Item, Guid, Enclosure, Feed, Image
import podme_api
from podme_api.exceptions import AccessDeniedError

from config import Config
from exceptions import InvalidConfigError
from utils import date_of_episode

BASE_CONFIG_PATH = "config/base_config.yaml"

CONFIG_PATH = "config/config.yaml"

conf = Config.from_config_file(CONFIG_PATH, BASE_CONFIG_PATH)


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
        print(f"[INFO] Nothing new from '{slug}', all available episodes of already harvested")
        return
    print(
        f"[INFO] Found {len(to_harvest)} new episode{'s' if len(to_harvest) > 1 else ''} of '{slug}' ready to harvest")
    podcast_dir = conf.get_podcast_dir(slug)
    os.makedirs(podcast_dir, exist_ok=True)
    # harvest each missing episode
    for episode_id in to_harvest:
        client.download_episode(
            f"{podcast_dir}/{episode_id}.mp3",
            client.get_episode_info(episode_id)['streamUrl']
        )
    sync_feed(client, slug)


def harvested_episodes(client, slug):
    return [client.get_episode_info(e) for e in harvested_episode_ids(client, slug)]


def harvested_episode_ids(client, slug):
    podcast_dir = conf.get_podcast_dir(slug)
    if not os.path.isdir(podcast_dir):
        # no directory, so clearly no harvested episodes
        return []
    episode_ids = client.get_episode_ids(slug)
    harvested = []
    for filename in os.listdir(podcast_dir):
        m = re.match(r'(.*)\.mp3$', filename)
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
    os.makedirs(conf.get_podcast_dir(slug), exist_ok=True)
    with open(conf.get_podcast_feed_path(slug), "w") as feed_file:
        feed_file.write(feed)
    print(f"[INFO] '{slug}' feed now serving {len(episodes)} episode{'s' if len(episodes) != 1 else ''}")


def build_feed(episodes, slug, title, description, image_url):
    items = []
    for e in episodes:
        episode_path = f"{conf.get_podcast_dir(slug)}/{e['id']}.mp3"
        items.append(Item(
            title=e['title'],
            description=e['description'],
            guid=Guid(e['id'], isPermaLink=False),
            enclosure=Enclosure(
                url=f'{conf.host}/{episode_path}',
                type='audio/mpeg',
                length=os.stat(episode_path).st_size
            ),
            pubDate=date_of_episode(e)
        ))
    feed_link = f"{conf.host}/{conf.get_podcast_feed_path(slug)}"
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
        items=sorted(items, key=lambda i: i.pubDate, reverse=True)
    )
    return feed.rss()


def main():
    if len(sys.argv) > 1:
        if conf is None:
            raise InvalidConfigError(f"No config defined")
        op = sys.argv[1]
        if op in ["harvest", "sync_feed"]:
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
                elif op == "sync_feed":
                    sync_feed(podme_client, slug)
            else:
                if op == "harvest":
                    harvest_all(podme_client)
                elif op == "sync_feed":
                    sync_all_feeds(podme_client)
        else:
            print("[FAIL] Argument must be either 'harvest' or 'sync_feed'")
    else:
        print(
            "[FAIL] Missing operation argument. Use 'harvest' to grab new episodes, or 'sync_feed' to update RSS feed")


if __name__ == '__main__':
    main()
