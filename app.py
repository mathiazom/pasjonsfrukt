import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import Config
from definitions import APP_ROOT

app = FastAPI()

conf = Config.from_config_file(
    path=APP_ROOT / "config" / "config.yaml",
    base_path=APP_ROOT / "config" / "base_config.yaml"
)

# Use absolute path to avoid dependency on working directory
absolute_yield_dir = APP_ROOT / conf.yield_dir

# Make sure yield directory exists
os.makedirs(absolute_yield_dir, exist_ok=True)

# Mount yield directory as static files to yield path
app.mount(f"/{conf.yield_dir}", StaticFiles(directory=absolute_yield_dir), name="static")
