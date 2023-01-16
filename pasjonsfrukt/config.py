from dataclasses import dataclass
from io import TextIOWrapper
from typing import Optional

from dataclass_wizard import YAMLWizard


@dataclass
class Auth:
    email: str
    password: str


@dataclass
class Podcast:
    feed_name: Optional[str] = "feed"


@dataclass
class Config(YAMLWizard):
    host: str
    auth: Auth
    podcasts: dict[str, Optional[Podcast]]  # Podcast is not actually optional, see __post_init__
    yield_dir: str = "yield"
    secret: Optional[str] = None

    def __post_init__(self):
        # All Podcast properties are currently optional, but default values need to be initialized
        # This allows the YAML config to specify a podcast without an otherwise required empty object ("{}")
        self.podcasts = {k: (v if v is not None else Podcast()) for k, v in self.podcasts.items()}


def config_from_stream(stream: TextIOWrapper) -> Optional[Config]:
    return Config.from_yaml(stream)
