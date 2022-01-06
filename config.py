from pathlib import Path

import yaml
from munch import Munch

import collections.abc

from exceptions import InvalidConfigError


class Config(Munch):
    """Glorified Munch object for handling harvesting configurations"""

    @classmethod
    def from_yaml(cls, path):
        """Create config object from YAML config file"""
        with open(path) as file:
            try:
                config = yaml.safe_load(file)
                return cls.fromDict(config)
            except yaml.YAMLError as exc:
                print(f"[FAIL] Error while loading YAML config: {exc}")

    @classmethod
    def from_config_file(cls, path, base_path):
        """Create new config by extending and overriding a base config"""
        config = cls.fromDict(cls.from_yaml(path))
        base_config = cls.fromDict(cls.from_yaml(base_path))
        base_config.deep_update(config)  # override and extend
        base_config.fill_podcast_configs()
        base_config.validate()
        return base_config

    def fill_podcast_configs(self):
        """Fill missing podcast configs with default values"""
        if "podcasts" not in self or self.podcasts is None:
            return
        updated_podcasts = Config()
        for slug, config in self.podcasts.items():
            base_podcast_config = Config.fromDict(self.defaults)
            base_podcast_config.deep_update(config)
            updated_podcasts[slug] = base_podcast_config
        self.podcasts.update(updated_podcasts)

    def deep_update(self, overrides):
        """
        Update a nested dictionary or similar mapping.
        Modify self` in place.
        """
        if overrides is None:
            return
        for key, value in overrides.items():
            if isinstance(value, collections.abc.Mapping) and value:
                to_update = self.get(key, Config())
                to_update.deep_update(value)
                self[key] = to_update
            elif value is not None or key not in self:
                self[key] = overrides[key]

    def get_podcast_dir(self, slug):
        return Path(self.yield_dir) / slug

    def get_podcast_feed_path(self, slug):
        return self.get_podcast_dir(slug) / f"{self.podcasts.get(slug).feed_name}.xml"

    def validate(self):
        for non_optional in ['host', 'podcasts']:
            if non_optional not in self:
                raise InvalidConfigError(f"Non-optional '{non_optional}' not defined")
        if self.podcasts is None:
            raise InvalidConfigError(f"No podcasts defined")
