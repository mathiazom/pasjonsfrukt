# pasjonsfrukt

### Setup
1. Install required Python dependencies
```
pip install -r requirements
```
2. Install [`ffmpeg`](https://ffmpeg.org/) (required by `youtube-dl` for the `m3u8` format).

3. Define harvest configurations by copying `config/config.dist.yaml` to your own `config/config.yaml`.  
Most importantly, you need to provide a `host` path (for links in RSS feed), login credentials for you PodMe account, and a list of the podcasts you wish to harvest.  
See `config/config.example.yaml` for a sample configuration.

### Usage

Harvest episodes
```sh
python pasjonsfrukt.py harvest
```

Update RSS feed
```sh
python pasjonsfrukt.py sync_feed
```
> The feed is always updated after harvest, so manual feed syncing is usually not required

Run webserver to serve RSS feed on `/<yield_dir>/<feed_name>.xml`
```sh
uvicorn app:app
```
> `yield_dir` and `feed_name` can be defined in the config file.
