import logging
from typing import Optional, Annotated
import typer
import uvicorn
import pprint

from . import api
from .api import api as api_app, api_config
from .async_cli import AsyncTyper
from .config import config_from_stream
from .logging_utils import LogRedactSecretFilter
from .main import get_podme_client, sync_slug_feed, harvest_podcast

cli = AsyncTyper()


@cli.command()
async def harvest(
    podcast_slugs: Annotated[
        Optional[list[str]],
        typer.Argument(
            metavar="[PODCAST_SLUG]...",
        ),
    ] = None,
    config_stream: Annotated[
        Optional[typer.FileText],
        typer.Option(
            "--config-file",
            "-c",
            encoding="utf-8",
            help="Configurations file",
        ),
    ] = "config.yaml",
):
    """
    Scrape podcast episodes
    """
    config = config_from_stream(config_stream)
    async with get_podme_client(config.auth.email, config.auth.password) as client:
        to_harvest = config.podcasts.keys() if podcast_slugs is None else podcast_slugs
        for s in to_harvest:
            await harvest_podcast(client, config, s)


@cli.command("sync")
async def sync_feeds(
    podcast_slugs: Annotated[
        Optional[list[str]],
        typer.Argument(
            metavar="[PODCAST_SLUG]...",
        ),
    ] = None,
    config_stream: Annotated[
        Optional[typer.FileText],
        typer.Option(
            "--config-file",
            "-c",
            encoding="utf-8",
            help="Configurations file",
        ),
    ] = "config.yaml",
):
    """
    Update RSS podcast feeds to match scraped episodes
    """
    config = config_from_stream(config_stream)
    async with get_podme_client(config.auth.email, config.auth.password) as client:
        to_sync = config.podcasts.keys() if podcast_slugs is None else podcast_slugs
        for s in to_sync:
            await sync_slug_feed(client, config, s)


@cli.command(
    name="serve",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },  # Enabled to support uvicorn options
)
def serve_api(
    ctx: typer.Context,
    config_stream: Annotated[
        Optional[typer.FileText],
        typer.Option(
            "--config-file",
            "-c",
            encoding="utf-8",
            help="Configurations file",
        ),
    ] = "config.yaml",
):
    """
    Serve RSS podcast feeds

    Wrapper around uvicorn, and supports passing additional options to the underlying uvicorn.run() command.
    """
    ctx.args.insert(0, f"{api.__name__}:api")
    config = config_from_stream(config_stream)
    api_app.dependency_overrides[api_config] = lambda: config
    if config.secret is not None:
        logging.getLogger("uvicorn.access").addFilter(
            LogRedactSecretFilter([config.secret])
        )
    uvicorn.main.main(args=ctx.args)


@cli.command(name="config")
def print_config(
    config_stream: Annotated[
        Optional[typer.FileText],
        typer.Option(
            "--config-file",
            "-c",
            encoding="utf-8",
            help="Configurations file",
        ),
    ] = "config.yaml",
):
    """
    Print parsed config
    """
    pprint.pprint(config_from_stream(config_stream))


@cli.callback()
def callback():
    """
    Scrape PodMe podcast streams to mp3 and host with RSS feed
    """
