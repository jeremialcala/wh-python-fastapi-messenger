# -*- coding: utf-8 -*-
"""
    This is an interface for logging utilities.
"""
import yaml


def configure_logging():
    """
        This method generates a logging configuration using a yaml file.
    :return: this config variable have an assortment of configurations to be used by logging.config.
    """
    with open('logging_config.yaml', 'rt', encoding='utf-8') as f:
        config = yaml.safe_load(f.read())
    return config
