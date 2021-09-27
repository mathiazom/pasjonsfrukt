import os
import re
import sys
from datetime import datetime

import requests
from starlette.responses import Response
from rfeed import Item, Guid, Enclosure, Feed, Image

import harvester
import locator

from dotenv import load_dotenv

load_dotenv()

YIELD_DIRECTORY = os.environ['YIELD_DIRECTORY']

EPISODES_API_URL = "https://api.podme.com/web/api/v2/episode/slug/papaya"

if not os.path.isdir(YIELD_DIRECTORY):
    os.mkdir(YIELD_DIRECTORY)

RSS_PATH = f"{YIELD_DIRECTORY}/feed.xml"


class RSSResponse(Response):
    media_type = 'application/xml'
    charset = 'utf-8'


def full_path_for_episode(e):
    return f'https://pasjonsfrukt.biku.be/{YIELD_DIRECTORY}/{e["id"]}.mp3'


def path_for_episode(e):
    return f'{YIELD_DIRECTORY}/{e["id"]}.mp3'


def harvest():
    inventory_path = f"inventory.txt"
    # create inventory file if it does not exist
    if not os.path.isfile(inventory_path):
        open(inventory_path, "x").close()
    # retrieve already harvested episodes
    with open(inventory_path, "r") as inventory:
        harvested = [line.strip() for line in inventory.readlines()]
    to_harvest = list(set(locator.scrape_episode_ids()) - set(harvested))
    if len(to_harvest) == 0:
        print("[INFO] Nothing new, all available episodes already harvested")
        return
    print(f"[INFO] Found {len(to_harvest)} new episode{'s' if len(to_harvest) > 1 else ''} ready to harvest")
    # harvest each missing episode
    with open(inventory_path, "a+") as inventory:
        for episode_id, date, remote_path in locator.locate(to_harvest):
            success = harvester.harvest(f"{YIELD_DIRECTORY}/{episode_id}.mp3", remote_path)
            if success:
                inventory.write(episode_id + "\n")
    sync_rss()


def harvested_episodes():
    episode_data = requests.get(EPISODES_API_URL).json()
    episodes_by_date = {str(e['id']): e for e in episode_data}
    harvested = []
    for filename in os.listdir(YIELD_DIRECTORY):
        m = re.match(r'(.*)\.mp3', filename)
        if m is not None:
            episode_id = m.group(1)
            if episode_id in episodes_by_date:
                harvested.append(episodes_by_date[episode_id])
    return harvested


def sync_rss():
    print(f"[INFO] Updating RSS feed...")
    episodes = harvested_episodes()
    rss = build_rss(episodes)
    with open(RSS_PATH, "w") as rss_file:
        rss_file.write(rss)
    print(f"[INFO] RSS now serving {len(episodes)} episode{'s' if len(episodes) > 1 else ''}")


def build_rss(episodes):
    items = []
    for e in episodes:
        date_iso_str = re.sub(r'\.\d*', "", e['dateAdded'])
        try:
            date = datetime.fromisoformat(date_iso_str)
        except ValueError:
            print("[ERROR] Invalid ISO date string")
            try:
                # Try again with just the date part
                date = datetime.fromisoformat(e['dateAdded'][:10])
            except ValueError:
                date = datetime.now()
        guid = e['id']
        items.append(Item(
            title=e['title'],
            description=e['description'],
            guid=Guid(guid, isPermaLink=False),
            enclosure=Enclosure(
                url=full_path_for_episode(e),
                type='audio/mpeg',
                length=os.stat(path_for_episode(e)).st_size
            ),
            pubDate=date
        ))

    feed = Feed(
        title="Pasjonsfrukt",
        link="https://pasjonsfrukt.biku.be/rss",
        description="Tre fete typer prøver seg i det private næringsliv.",
        language="no",
        image=Image(
            url='https://podmestorage.blob.core.windows.net/podcast-images/1ed3d6f17ef641b09a133464d128e8cb_medium.jpg',
            title='Pasjonsfrukt',
            link='https://pasjonsfrukt.biku.be/rss'
        ),
        items=items
    )

    return feed.rss()


if len(sys.argv) > 1:
    if sys.argv[1] == "harvest":
        harvest()
    elif sys.argv[1] == "rss":
        sync_rss()
    else:
        print("[FAIL] Argument must be either 'harvest' or 'rss'")
else:
    print("[FAIL] Missing operation argument. Use 'harvest' to grab new episodes, or 'rss' to update RSS feed")
