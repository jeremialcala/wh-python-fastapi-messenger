# -*- coding: utf-8 -*-
"""
    This is the services main class.

    Microservicio de procesamiento de mensajería Meta: consume webhooks de
    Messenger/WhatsApp/Instagram desde RabbitMQ, aplica guardrails, detecta la
    intención con Ollama y publica el resultado clasificado.
"""
import sys
import logging
import logging.config
from inspect import currentframe

from src.infrastructure.config import Settings
from src.infrastructure.logging import configure_logging
from src.infrastructure.shared import STARTING_AT, ENDING_AT, documenting_parameter
from src.presentation import run

_set = Settings()
logging.config.dictConfig(configure_logging())
log = logging.getLogger(_set.environment)


@documenting_parameter(_set.queue_name)
def get_help():
    """
    This get messages from a AMQP queue ({0}), classifies Meta messages and
    publishes the result.

    Args:


    """


if __name__ == "__main__":
    log.info(STARTING_AT, currentframe().f_code.co_name)

    if "--help" in sys.argv:
        print(get_help.__doc__)
        sys.exit(0)

    run(_set)

    log.info(ENDING_AT, currentframe().f_code.co_name)
    sys.exit(0)
