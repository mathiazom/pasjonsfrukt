# 🍹 pasjonsfrukt

### Setup
1. Install required Python dependencies
```
pip install -r requirements
```
2. Install [`ffmpeg`](https://ffmpeg.org/) (required by `youtube-dl` for the `m3u8` format).

3. Define harvest and feed configurations by copying `config/config.dist.yaml` to your own `config/config.yaml`.  
Most importantly, you need to provide:
  - a `host` path (for links in the RSS feeds)
  - login credentials (`auth`) for your PodMe account
  - the `podcasts` you wish to harvest.

  See `config/config.example.yaml` for a sample configuration.

### Usage

##### Harvest episodes

Harvest episodes of all podcasts defined in config
```sh
python pasjonsfrukt.py harvest
```

Harvest episodes of specific podcast
```sh
python pasjonsfrukt.py harvest <podcast-slug>
```

##### Update feeds
Update all RSS feeds defined in config
```sh
python pasjonsfrukt.py sync
```

Update RSS feed of specific podcast
```sh
python pasjonsfrukt.py sync <podcast-slug>
```

> The feeds are always updated after harvest, so manual feed syncing is usually not required

##### Serve feeds and episodes

Run web server
```sh
uvicorn app:app
```
RSS feeds will be served at `/<yield_dir>/<podcast_slug>`, while episode files are served at `/<yield_dir>/<podcast_slug>/<episode_id>`

> `yield_dir` can be defined in the config file.

##### Secret
If a `secret` has been defined in the config, a query parameter (`?secret=<secret-string>`) with matching secret string is required to access the served podcast feeds and episode files. This is useful for making RSS feeds accessible on the web, without making them fully public. Still, the "secrecy" is provided as is, with no warranties.
