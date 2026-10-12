import yaml
import logging.config
from pathlib import Path
from classes import Settings

# Next to the code, not in the working directory: the app starts the same from the repo root and from the image.
LOGGING_CONFIG = Path(__file__).resolve().parent.parent / "logging_config.yaml"


def configure_logging():
    with open(LOGGING_CONFIG, 'rt') as f:
        config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)

