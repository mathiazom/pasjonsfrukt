import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

YIELD_DIRECTORY = os.environ['YIELD_DIRECTORY']
app.mount(f"/{YIELD_DIRECTORY}", StaticFiles(directory=YIELD_DIRECTORY), name="static")
