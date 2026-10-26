# 🍹 pasjonsfrukt

[![pasjonsfrukt](https://img.shields.io/badge/ghcr.io-mathiazom%2Fpasjonsfrukt-blue?logo=docker)](https://github.com/users/mathiazom/packages/container/package/pasjonsfrukt)

Scrape PodMe podcast streams to mp3 and host with RSS feed.

<i style="color:grey">Note: A valid PodMe subscription is required to access premium content</i>

## Setup

### CLI

1. Clone repo
2. Install [`poetry`](https://python-poetry.org/)
3. Install dependencies

```
poetry install
```

4. Install [`ffmpeg`](https://ffmpeg.org/)

5. Define harvest and feed configurations by copying [`config.template.yaml`](config.template.yaml) to your own `config.yaml`.  
   Most importantly, you need to provide:

   - a `host` path (for links in the RSS feeds)
   - login credentials (`auth`) for your PodMe account
   - the `podcasts` you wish to harvest and serve

### Docker

Latest image is published at `ghcr.io/mathiazom/pasjonsfrukt:main`.

**Docker Compose**: use the [`docker-compose.template.yml`](./docker/docker-compose.template.yml) as a starting point.

Remember to map the config file and yield directory. An optional crontab can be mounted for periodic harvesting.

The Docker image serves the podcast feeds via `pasjonsfrukt serve`.

## Usage

### Harvest episodes

Harvest episodes of all podcasts defined in config

```sh
pasjonsfrukt harvest
```

Harvest episodes of specific podcast(s)

```sh
pasjonsfrukt harvest [PODCAST_SLUG]...
```

### Update feeds

Update all RSS feeds defined in config

```sh
pasjonsfrukt sync
```

Update RSS feed of specific podcast

```sh
pasjonsfrukt sync [PODCAST_SLUG]...
```

> The feeds are always updated after harvest, so manual feed syncing is only required if files are changed externally

### Serve RSS feeds with episodes

Run web server

```sh
pasjonsfrukt serve
```

RSS feeds will be served at `<host>/<podcast_slug>`, while episode files are served
at `<host>/<podcast_slug>/<episode_id>`

> `host` must be defined in the config file.

### Secret

If a `secret` has been defined in the config, a query parameter (`?secret=<secret-string>`) with matching secret string
is required to access the served podcast feeds and episode files. This is useful for making RSS feeds accessible on the
web, without making them fully public. Still, the confidentiality is provided as is, with no warranties 🙃

## Development

### Formatting

```commandline
poe fmt
```
> uses [Black](https://black.readthedocs.io/en/stable/) code formatter
