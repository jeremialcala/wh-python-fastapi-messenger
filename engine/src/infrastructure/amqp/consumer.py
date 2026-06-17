# -*- coding: utf-8 -*-
"""
    Consumidor AMQP (RabbitMQ). Mantiene el modelo de procesamiento por hilos
    con ACK threadsafe del template original, pero desacoplado del dominio: el
    procesamiento de cada mensaje se delega en un `handler` inyectado.
"""
import threading
import functools
import logging.config
from inspect import currentframe
from typing import Callable

import pika
from pika.channel import Channel

from src.infrastructure.config import Settings
from src.infrastructure.logging import configure_logging
from src.infrastructure.shared import STARTING_AT, ENDING_AT

_set = Settings()
log = logging.getLogger(__name__)
logging.getLogger("pika").propagate = False
logging.config.dictConfig(configure_logging())


def get_amqp_connection_parameters(host=_set.qms_server, port=_set.qms_port):
    """
    :return: pika Connection parameters for RabbitMQ.
    """
    log.info(STARTING_AT, currentframe().f_code.co_name)
    credentials = pika.credentials.PlainCredentials(username=_set.qms_user,
                                                    password=_set.qms_password)
    conn_parameters = pika.ConnectionParameters(host=host, port=port,
                                                credentials=credentials)
    log.info(ENDING_AT, currentframe().f_code.co_name)
    return conn_parameters


def ack_message(channel, delivery_tag) -> None:
    """
        Note that `channel` must be the same pika channel instance via which
        the message being ACKed was retrieved (AMQP protocol constraint).
    """
    log.info(STARTING_AT, currentframe().f_code.co_name)
    if channel.is_open:
        channel.basic_ack(delivery_tag)
    log.info(ENDING_AT, currentframe().f_code.co_name)


class AmqpConsumer:
    """
        Escucha activa sobre una cola de RabbitMQ. Por cada mensaje lanza un
        hilo que ejecuta el `handler` y, al terminar, confirma (ACK) de forma
        threadsafe.
    """

    def __init__(self, handler: Callable[[bytes], None], connection_parameters=None):
        """
        :param handler: función que procesa el cuerpo crudo del mensaje (bytes).
        :param connection_parameters: parámetros pika; por defecto los del entorno.
        """
        self._handler = handler
        self._params = connection_parameters or get_amqp_connection_parameters()

    def start(self, queue: str = _set.queue_name,
              exchange: str = _set.amqp_exchange,
              routing_key: str = _set.amqp_routing_key) -> None:
        """
            Declara/enlaza la cola y comienza a consumir.
        """
        log.info(STARTING_AT, currentframe().f_code.co_name)
        threads: list[threading.Thread] = []
        connection = pika.BlockingConnection(self._params)

        channel = connection.channel()
        channel.queue_declare(queue=queue, auto_delete=False, durable=False)
        channel.queue_bind(queue=queue, exchange=exchange, routing_key=routing_key)
        channel.basic_qos(prefetch_count=1)

        on_message_callback = functools.partial(self._on_message, args=(connection, threads))
        channel.basic_consume(queue=queue, on_message_callback=on_message_callback)
        channel.start_consuming()

        for thread in threads:
            thread.join()
        log.info(ENDING_AT, currentframe().f_code.co_name)

    def _on_message(self, channel: Channel, method_frame, _header_frame, body, args) -> None:
        """
            Callback de pika: lanza un hilo para procesar el mensaje.
        """
        log.info(STARTING_AT, currentframe().f_code.co_name)
        (_connection, _threads) = args
        t = threading.Thread(
            target=self._execute,
            args=(_connection, channel, method_frame.delivery_tag, body)
        )
        t.start()
        _threads.append(t)
        log.info(ENDING_AT, currentframe().f_code.co_name)

    def _execute(self, connection, channel, delivery_tag, body) -> None:
        """
            Ejecuta el handler en el hilo y confirma el mensaje (ACK threadsafe).
        """
        log.info(STARTING_AT, currentframe().f_code.co_name)
        thread_id = threading.get_ident()
        log.info('Thread id: %s Delivery tag: %s', thread_id, delivery_tag)
        try:
            self._handler(body)
        except Exception:  # pylint: disable=broad-except
            log.exception("Error procesando mensaje delivery_tag=%s", delivery_tag)
        finally:
            cb = functools.partial(ack_message, channel, delivery_tag)
            connection.add_callback_threadsafe(cb)
        log.info(ENDING_AT, currentframe().f_code.co_name)
