# -*- coding: utf-8 -*-
"""
    This is the services main class
"""
import sys
import logging
import logging.config
from inspect import currentframe

from classes import Settings
from constants import STARTING_AT, ENDING_AT
from controllers import process_messages
from utils import configure_logging, documenting_parameter

_set = Settings()
logging.config.dictConfig(configure_logging())
log = logging.getLogger(_set.environment)


@documenting_parameter(_set.queue_name)
def get_help():
    """
    This get messages from a AMQP, and process operations on the {0} lifecycle.

    Args:


    """


if __name__ == "__main__":
    log.info(STARTING_AT, currentframe().f_code.co_name)

    if "--help" in sys.argv:
        print(get_help.__doc__)
        sys.exit(0)

    arg_name = [arg for arg in sys.argv if "--" in arg]

    process_messages(queue=_set.queue_name)

    log.info(ENDING_AT, currentframe().f_code.co_name)
    exit(0)

