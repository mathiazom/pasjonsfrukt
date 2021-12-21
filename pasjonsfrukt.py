import os
import re
import sys
from datetime import datetime

from starlette.responses import Response
from rfeed import Item, Guid, Enclosure, Feed, Image
import podme_api
from podme_api.exceptions import AccessDeniedError

PODCAST_SLUG = "papaya"

YIELD_DIRECTORY = os.environ['PASJONSFRUKT_YIELD_DIRECTORY']

RSS_DIRECTORY = YIELD_DIRECTORY

RSS_FEED_NAME = "feed.xml"


class RSSResponse(Response):
    media_type = 'application/xml'
    charset = 'utf-8'


def full_path_for_episode(e):
    return f'https://pasjonsfrukt.biku.be/{YIELD_DIRECTORY}/{e["id"]}.mp3'


def path_for_episode(e):
    return f'{YIELD_DIRECTORY}/{e["id"]}.mp3'


def harvest(client, slug):
    harvested_ids = harvested_episode_ids(client, slug)
    published_ids = client.get_episode_ids(slug)
    to_harvest = [e for e in published_ids if e not in harvested_ids]
    if len(to_harvest) == 0:
        print("[INFO] Nothing new, all available episodes already harvested")
        return
    print(f"[INFO] Found {len(to_harvest)} new episode{'s' if len(to_harvest) > 1 else ''} ready to harvest")
    # create yield directory if it does not exist
    if not os.path.isdir(YIELD_DIRECTORY):
        os.mkdir(YIELD_DIRECTORY)
    # harvest each missing episode
    for episode_id in to_harvest:
        client.download_episode(
            f"{YIELD_DIRECTORY}/{episode_id}.mp3",
            client.get_episode_info(episode_id)['streamUrl']
        )
    sync_rss(client, slug)


def harvested_episode_ids(client, slug):
    if not os.path.isdir(YIELD_DIRECTORY):
        return []
    episode_ids = client.get_episode_ids(slug)
    harvested = []
    for filename in os.listdir(YIELD_DIRECTORY):
        m = re.match(r'(.*)\.mp3', filename)
        if m is not None:
            episode_id = int(m.group(1))
            if episode_id in episode_ids:
                harvested.append(episode_id)
    return harvested


def harvested_episodes(client, slug):
    return [client.get_episode_info(e) for e in harvested_episode_ids(client, slug)]


def sync_rss(client, slug):
    print(f"[INFO] Updating RSS feed...")
    episodes = harvested_episodes(client, slug)
    rss = build_rss(episodes)
    # create RSS directory if it does not exist
    if not os.path.isdir(RSS_DIRECTORY):
        os.mkdir(RSS_DIRECTORY)
    with open(f"{RSS_DIRECTORY}/{RSS_FEED_NAME}", "w") as rss_file:
        rss_file.write(rss)
    print(f"[INFO] RSS now serving {len(episodes)} episode{'s' if len(episodes) != 1 else ''}")


def date_of_episode(episode):
    date_iso_str = re.sub(r'\.\d*', "", episode['dateAdded'])
    try:
        return datetime.fromisoformat(date_iso_str)
    except ValueError:
        print("[ERROR] Invalid ISO date string")
        try:
            # Try again with just the date part
            return datetime.fromisoformat(episode['dateAdded'][:10])
        except ValueError:
            return datetime.now()


def build_rss(episodes):
    items = []
    for e in episodes:
        items.append(Item(
            title=e['title'],
            description=e['description'],
            guid=Guid(e['id'], isPermaLink=False),
            enclosure=Enclosure(
                url=full_path_for_episode(e),
                type='audio/mpeg',
                length=os.stat(path_for_episode(e)).st_size
            ),
            pubDate=date_of_episode(e)
        ))

    feed = Feed(
        title="Pasjonsfrukt",
        link="https://pasjonsfrukt.biku.be/rss",
        description="Tre fete typer prøver seg i det private næringsliv.",
        language="no",
        image=Image(
            url='https://pasjonsfrukt.biku.be/media/pasjonsfrukt.jpg',
            title='Pasjonsfrukt',
            link='https://pasjonsfrukt.biku.be/rss'
        ),
        items=sorted(items, key=lambda i: i.pubDate, reverse=True)
    )

    return feed.rss()


def main():
    if len(sys.argv) > 1:
        op = sys.argv[1]
        if op in ["harvest", "rss"]:
            podme_client = podme_api.PodMeClient(
                email=os.environ["PASJONSFRUKT_PODME_EMAIL"],
                password=os.environ["PASJONSFRUKT_PODME_PASSWORD"]
            )
            try:
                podme_client.login()
            except AccessDeniedError:
                print("[FAIL] Access denied when retrieving PodMe token, please check your login credentials")
                return
            if op == "harvest":
                harvest(podme_client, PODCAST_SLUG)
            elif op == "rss":
                sync_rss(podme_client, PODCAST_SLUG)
        else:
            print("[FAIL] Argument must be either 'harvest' or 'rss'")
    else:
        print("[FAIL] Missing operation argument. Use 'harvest' to grab new episodes, or 'rss' to update RSS feed")


if __name__ == '__main__':
    main()
