import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import Config

app = FastAPI()

conf = Config.from_config_file(
    path="config/config.yaml",
    base_path="config/base_config.yaml"
)

# Use absolute path to avoid dependence on working directory
absolute_yield_dir = os.path.join(os.path.dirname(__file__), conf.yield_dir)

# Make sure yield directory exists
os.makedirs(absolute_yield_dir, exist_ok=True)

# Mount yield directory as static files to yield path
app.mount(f"/{conf.yield_dir}", StaticFiles(directory=absolute_yield_dir), name="static")
