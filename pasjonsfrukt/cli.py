import logging

import typer
import uvicorn
import pprint

from . import api
from .api import api as api_app, api_config
from .async_cli import AsyncTyper
from .config import config_from_stream
from .logging_utils import LogRedactSecretFilter, get_logging_level
from .main import get_podme_client, sync_slug_feed, harvest_podcast, sync_index

cli = AsyncTyper()


@cli.command()
async def harvest(
    podcast_slugs: list[str] = typer.Argument(
        None,  # NB: default is actually an empty list | TODO: #108 at tiangolo/typer
        metavar="[PODCAST_SLUG]...",
    ),
    config_stream: typer.FileText = typer.Option(
        "config.yaml",
        "--config-file",
        "-c",
        encoding="utf-8",
        help="Configurations file",
    ),
):
    """
    Scrape podcast episodes
    """
    config = config_from_stream(config_stream)
    async with get_podme_client(config.auth.email, config.auth.password) as client:
        to_harvest = (
            config.podcasts.keys() if len(podcast_slugs) == 0 else podcast_slugs
        )
        for s in to_harvest:
            await harvest_podcast(client, config, s)

        podcasts = await client.get_podcasts_info(to_harvest)
        await sync_index(config, podcasts)


@cli.command("sync")
async def sync_feeds(
    podcast_slugs: list[str] = typer.Argument(
        None,  # NB: default is actually an empty list | TODO: #108 at tiangolo/typer
        metavar="[PODCAST_SLUG]...",
    ),
    config_stream: typer.FileText = typer.Option(
        "config.yaml",
        "--config-file",
        "-c",
        encoding="utf-8",
        help="Configurations file",
    ),
):
    """
    Update RSS podcast feeds to match scraped episodes
    """
    config = config_from_stream(config_stream)
    async with get_podme_client(config.auth.email, config.auth.password) as client:
        to_sync = config.podcasts.keys() if len(podcast_slugs) == 0 else podcast_slugs
        for s in to_sync:
            await sync_slug_feed(client, config, s)

        podcasts = await client.get_podcasts_info(to_sync)
        await sync_index(config, podcasts)


@cli.command(
    name="serve",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },  # Enabled to support uvicorn options
)
def serve_api(
    ctx: typer.Context,
    config_stream: typer.FileText = typer.Option(
        "config.yaml",
        "--config-file",
        "-c",
        encoding="utf-8",
        help="Configurations file",
    ),
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
    config_stream: typer.FileText = typer.Option(
        "config.yaml",
        "--config-file",
        "-c",
        encoding="utf-8",
        help="Configurations file",
    ),
):
    """
    Print parsed config
    """
    pprint.pprint(config_from_stream(config_stream))


@cli.callback()
def callback(
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        help="Enable verbose output. Repeat for increased verbosity.",
        show_default=False,
        metavar="",
        count=True,
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debugging.",
        show_default=False,
        is_flag=True,
    ),
):
    """
    Scrape PodMe podcast streams to mp3 and host with RSS feed
    """
    logging.basicConfig(level=get_logging_level(verbose, debug))
