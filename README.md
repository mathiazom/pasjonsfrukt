# pasjonsfrukt

### Setup
1. Install required Python dependencies
```
pip install -r requirements
```
2. Install [`ffmpeg`](https://ffmpeg.org/) (required by `youtube-dl` for the `m3u8` format).

3. Add PodMe credentials as environment variables
(you can use `.env.dist` as a template for your own `.env`)
```sh
PASJONSFRUKT_PODME_EMAIL=your@podme.email
PASJONSFRUKT_PODME_PASSWORD=yourpodmepassword
```

### Usage

Harvest episodes
```sh
python pasjonsfrukt.py harvest
```

Update RSS feed
```sh
python pasjonsfrukt.py rss
```
> The RSS feed is always updated after harvest, so this should in theory never be required...

Run webserver to serve RSS feed on `/f/feed.xml`
```sh
uvicorn app:app
```
> The feed and media files path can be changed via the `YIELD_DIRECTORY` env variable to produce paths on the form `/YIELD_DIRECTORY/feed.xml` and `/YIELD_DIRECTORY/561509.mp3`
