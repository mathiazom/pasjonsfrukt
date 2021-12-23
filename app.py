import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

YIELD_DIRECTORY = os.environ['PASJONSFRUKT_YIELD_DIRECTORY']
app.mount(f"/{YIELD_DIRECTORY}", StaticFiles(directory=YIELD_DIRECTORY), name="static")
