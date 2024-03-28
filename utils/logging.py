import yaml
import logging.config
from classes import Settings


def configure_logging():
    with open('logging_config.yaml', 'rt') as f:
        config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)

