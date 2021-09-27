import json
import os
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait

import requests


def scrape_episode_ids():
    episodes = requests.get("https://api.podme.com/web/api/v2/episode/slug/papaya").json()
    return [str(e['id']) for e in episodes]


def locate(episodes):
    firefox_options = Options()
    firefox_options.add_argument("-headless")
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.get("https://podme.com/no/")
        WebDriverWait(driver, timeout=20).until(
            lambda d: d.find_element_by_class_name("login-button"),
            "Failed to find login button"
        ).click()
        WebDriverWait(driver, timeout=20).until(
            lambda d: d.find_element_by_id("logonIdentifier"),
            "Failed to find email input"
        ).send_keys(os.environ["PODME_EMAIL"])
        WebDriverWait(driver, timeout=20).until(
            lambda d: d.find_element_by_id("password"),
            "Failed to find password input"
        ).send_keys(os.environ["PODME_PASSWORD"])
        WebDriverWait(driver, timeout=20).until(
            lambda d: d.find_element_by_id("next"),
            "Failed to find login submit button"
        ).click()
        time.sleep(5)
        hello_storage = driver.execute_script("return window.localStorage.getItem('hello')")
        token = json.loads(hello_storage)['adB2CSignIn']['access_token']
    stream_urls = []
    for episode_id in episodes:
        res = requests.get(f"https://api.podme.com/web/api/v2/episode/{episode_id}", headers={
            "Authorization": f"Bearer {token}"
        })
        episode_json = res.json()
        stream_url = episode_json['streamUrl']
        date = episode_json['dateAdded'][:10]
        print(stream_url)
        stream_urls.append((episode_id, date, stream_url))
    return stream_urls
