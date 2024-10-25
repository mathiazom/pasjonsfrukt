# 🍹 pasjonsfrukt

[![PyPI](https://img.shields.io/pypi/v/pasjonsfrukt)](https://pypi.org/project/pasjonsfrukt/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pasjonsfrukt)
[![PyPI - License](https://img.shields.io/pypi/l/pasjonsfrukt)](https://github.com/mathiazom/pasjonsfrukt/blob/main/LICENSE)

Scrape PodMe podcast streams to mp3 and host with RSS feed.

<i style="color:grey">Note: A valid PodMe subscription is required to access premium content</i>

### Setup

1. Install `pasjonsfrukt`

```
pip install pasjonsfrukt
```

2. Install [`ffmpeg`](https://ffmpeg.org/)

3. Define harvest and feed configurations by copying [`config.template.yaml`](config.template.yaml) to your own `config.yaml`.  
   Most importantly, you need to provide:

   - a `host` path (for links in the RSS feeds)
   - login credentials (`auth`) for your PodMe account
   - the `podcasts` you wish to harvest and serve

### Usage

##### Harvest episodes

Harvest episodes of all podcasts defined in config

```sh
pasjonsfrukt harvest
```

Harvest episodes of specific podcast(s)

```sh
pasjonsfrukt harvest [PODCAST_SLUG]...
```

##### Update feeds

Update all RSS feeds defined in config

```sh
pasjonsfrukt sync
```

Update RSS feed of specific podcast

```sh
pasjonsfrukt sync [PODCAST_SLUG]...
```

> The feeds are always updated after harvest, so manual feed syncing is only required if files are changed externally

##### Serve RSS feeds with episodes

Run web server

```sh
pasjonsfrukt serve
```

RSS feeds will be served at `<host>/<podcast_slug>`, while episode files are served
at `<host>/<podcast_slug>/<episode_id>`

> `host` must be defined in the config file.

##### Secret

If a `secret` has been defined in the config, a query parameter (`?secret=<secret-string>`) with matching secret string
is required to access the served podcast feeds and episode files. This is useful for making RSS feeds accessible on the
web, without making them fully public. Still, the confidentiality is provided as is, with no warranties 🙃
