# -*- coding: utf-8 -*-
"""
    Publicador AMQP: implementa el puerto `MessagePublisher` publicando el
    `ResultadoClasificado` en la cola de salida.
"""
import logging.config
from inspect import currentframe

import pika

from src.domain.models import ResultadoClasificado
from src.domain.ports import MessagePublisher
from src.infrastructure.config import Settings
from src.infrastructure.logging import configure_logging
from src.infrastructure.shared import STARTING_AT, ENDING_AT
from .consumer import get_amqp_connection_parameters

_set = Settings()
log = logging.getLogger(__name__)
logging.config.dictConfig(configure_logging())


def send_message_to_queue(queue: str, routing_key: str, message,
                          connection_parameters=None,
                          exchange: str = _set.amqp_exchange) -> None:
    """
        Publica un mensaje en una cola/exchange de RabbitMQ.
    """
    log.info(STARTING_AT, currentframe().f_code.co_name)
    connection = pika.BlockingConnection(
        connection_parameters or get_amqp_connection_parameters()
    )
    channel = connection.channel()
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange=exchange, routing_key=routing_key, body=message)
    connection.close()
    log.info(ENDING_AT, currentframe().f_code.co_name)


class AmqpPublisher(MessagePublisher):
    """
        Adaptador AMQP del puerto `MessagePublisher`.
    """

    def __init__(self, queue: str = _set.output_queue_name,
                 routing_key: str = _set.output_routing_key,
                 connection_parameters=None):
        self._queue = queue
        self._routing_key = routing_key
        self._params = connection_parameters

    def publicar(self, resultado: ResultadoClasificado) -> None:
        """
        :param resultado: resultado del pipeline a publicar como JSON.
        """
        send_message_to_queue(
            queue=self._queue,
            routing_key=self._routing_key,
            message=resultado.to_json(),
            connection_parameters=self._params,
        )
