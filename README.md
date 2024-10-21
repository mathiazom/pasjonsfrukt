# 🍹 pasjonsfrukt

Scrape PodMe podcast streams to mp3 and host with RSS feed.

<i style="color:grey">Note: A valid PodMe subscription is required to access premium content</i>

### Setup

1. Install `pasjonsfrukt`

```
pip install git+https://github.com/mathiazom/pasjonsfrukt.git@schibsted-auth
```
> this version is not available at PyPi yet becuase of an experimental version of the `podme_api` dependency

2. Install [`ffmpeg`](https://ffmpeg.org/) (required by dependency `youtube-dl` for the `m3u8` format).

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

### Serve using nginx

If you prefer hosting the RSS feeds and episode files on your own server, you can use [nginx](https://www.nginx.com/) with the following config.

```nginx
server {
    listen 8000;
    server_name _;

    root /path/to/podcasts;

    location / {
        # Redirect requests with trailing slash to non-trailing slash
        rewrite ^/(.*)/$ /$1 permanent;
        rewrite ^/(.*)/feed.xml /$1 redirect;

        # For requests to the base slug (e.g., /papaya)
        location ~ ^/[^/]+$ {
            try_files $uri $uri.xml $uri/$uri.xml =404;
        }

        location ~ \.mp3$ {
            sendfile           on;
            sendfile_max_chunk 1m;
        }

        try_files $uri =404;
    }
}
```
