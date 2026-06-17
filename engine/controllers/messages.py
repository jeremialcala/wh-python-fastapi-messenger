# -*- coding: utf-8 -*-
"""
    This controller will receive, process and send messages with the process result.

"""
import logging.config

import functools
from inspect import currentframe
import pika
from classes import Settings
from utils import configure_logging
from constants import STARTING_AT, ENDING_AT
from .amqp import get_amqp_connection_parameters, on_message
_set = Settings()

log = logging.getLogger(__name__)
logging.getLogger("pika").propagate = False
logging.config.dictConfig(configure_logging())


def process_messages(queue: str = _set.queue_name,
                     connection_parameters=get_amqp_connection_parameters()) -> None:
    """
        This method will open a queue and send using the AMQP controller to be processed

    """
    log.info(STARTING_AT, currentframe().f_code.co_name)
    threads = []
    connection = pika.BlockingConnection(connection_parameters)

    channel = connection.channel()
    channel.queue_declare(queue=queue, auto_delete=False, durable=False)
    channel.queue_bind(
        queue=queue,
        exchange=_set.amqp_exchange,
        routing_key=_set.amqp_routing_key
    )
    channel.basic_qos(prefetch_count=1)

    on_message_callback = functools.partial(on_message,
                                            args=(connection, threads))

    channel.basic_consume(queue=queue, on_message_callback=on_message_callback)
    channel.start_consuming()

    for thread in threads:
        thread.join()

    log.info(ENDING_AT, currentframe().f_code.co_name)
