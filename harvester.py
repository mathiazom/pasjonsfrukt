from __future__ import unicode_literals
from youtube_dl import YoutubeDL
from youtube_dl.utils import YoutubeDLError


class HarvestLogger(object):
    def debug(self, msg):
        print(msg)

    def warning(self, msg):
        print(msg)

    def error(self, msg):
        print(msg)


def harvest_hook(d):
    if d['status'] == 'finished':
        print('Done downloading, now converting ...')


def harvest(path, url):
    ydl_opts = {
        'logger': HarvestLogger(),
        'progress_hooks': [harvest_hook],
        'outtmpl': path
    }
    with YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            return True
        except YoutubeDLError:
            print(f"[FAIL] youtube-dl failed to harvest from {url} to {path}")
            return False
