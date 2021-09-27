# pasjonsfrukt

### Setup
```
pip install -r requirements
```

### Usage

Harvest episodes
```
python pasjonsfrukt.py harvest
```

Update RSS feed
```
python pasjonsfrukt.py rss
```

Run webserver to serve RSS feed on `/yield/feed.xml`
```
uvicorn app:app
```

### Requirements
- [`ffmpeg`](https://ffmpeg.org/) must be installed (required by `youtube-dl` for the `m3u8` format)
- `pip install -r requirements.txt`
