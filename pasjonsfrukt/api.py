from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse

from .config import Config
from .main import build_podcast_feed_path, build_podcast_episode_file_path

api = FastAPI()


class RSSResponse(FileResponse):
    media_type = 'application/xml'
    charset = 'utf-8'


@lru_cache()
def api_config() -> Optional[Config]:
    return None


def raise_for_secret(config: Config, secret):
    if config.secret is not None and secret != config.secret:
        if secret is None:
            raise HTTPException(status_code=401, detail="Authorization failed, missing secret")
        raise HTTPException(status_code=401, detail="Authorization failed, incorrect secret")


def raise_for_podcast_slug(config: Config, slug):
    if slug not in config.podcasts.keys():
        raise HTTPException(status_code=404, detail="Requested resource not found")


def file_response_if_exists(file_path):
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Requested resource not found")
    return FileResponse(str(file_path.resolve()))


@api.get(f"/{{slug}}")
async def get_feed(slug: str, secret: Optional[str] = None, config: Config = Depends(api_config)):
    raise_for_secret(config, secret)
    raise_for_podcast_slug(config, slug)
    return file_response_if_exists(build_podcast_feed_path(config, slug))


@api.get(f"/{{podcast_slug}}/{{episode_id}}")
async def get_episode(podcast_slug: str, episode_id: int, secret: Optional[str] = None,
                      config: Config = Depends(api_config)):
    raise_for_secret(config, secret)
    raise_for_podcast_slug(config, podcast_slug)
    return file_response_if_exists(build_podcast_episode_file_path(config, podcast_slug, episode_id))
