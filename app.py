from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from config import Config
from definitions import APP_ROOT

app = FastAPI()

conf = Config.from_config_file(
    path=APP_ROOT / "config" / "config.yaml",
    base_path=APP_ROOT / "config" / "base_config.yaml"
)


def verify_secret(secret):
    if "secret" in conf and conf.secret is not None and secret != conf.secret:
        if secret is None:
            raise HTTPException(status_code=401, detail="Authorization failed, missing secret")
        raise HTTPException(status_code=401, detail="Authorization failed, incorrect secret")


def verify_podcast_slug(slug):
    if slug not in conf.podcasts:
        raise HTTPException(status_code=404, detail="Requested resource not found")


def file_response_if_exists(file_path):
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Requested resource not found")
    return FileResponse(str(file_path.resolve()))


@app.get(f"/{conf.yield_dir}/{{slug}}")
async def get_feed(slug: str, secret: Optional[str] = None):
    verify_secret(secret)
    verify_podcast_slug(slug)
    return file_response_if_exists(APP_ROOT / conf.get_podcast_feed_path(slug))


@app.get(f"/{conf.yield_dir}/{{podcast_slug}}/{{episode_id}}")
async def get_episode(podcast_slug: str, episode_id: int, secret: Optional[str] = None):
    verify_secret(secret)
    verify_podcast_slug(podcast_slug)
    return file_response_if_exists(APP_ROOT / conf.yield_dir / podcast_slug / f"{episode_id}.mp3")
