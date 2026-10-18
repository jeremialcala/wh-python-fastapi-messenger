# -*- coding: utf8 -*-
import logging

import pika
from starlette.concurrency import run_in_threadpool

from classes import Settings, QueueMessage

__all__ = ["BrokerUnavailable", "send_message_to_queue"]

settings = Settings()
log = logging.getLogger(settings.environment)


# How long a message may wait for the response engine: 24 hours, in milliseconds and as text, which is how
# RabbitMQ takes it. Set on each message and not on the queue, so nobody has to declare the queue again.
MESSAGE_TTL = str(24 * 60 * 60 * 1000)


class BrokerUnavailable(Exception):
    """The message could not be handed to RabbitMQ."""


def _publish(queue: str, body: bytes):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.qms_server,
            credentials=pika.credentials.PlainCredentials(
                username=settings.qms_user,
                password=settings.qms_password
            ),
            # Meta retries a webhook that takes too long, so fail fast instead of hanging.
            connection_attempts=1,
            socket_timeout=5,
            blocked_connection_timeout=5,
        )
    )
    try:
        channel = connection.channel()
        # With confirms on, basic_publish raises unless the broker accepted the message.
        channel.confirm_delivery()
        channel.queue_declare(queue=queue, durable=True)
        channel.basic_publish(exchange='',
                              routing_key=queue,
                              body=body,
                              properties=pika.BasicProperties(delivery_mode=2, expiration=MESSAGE_TTL),
                              mandatory=True)
    finally:
        if connection.is_open:
            connection.close()


async def send_message_to_queue(queue: str, message: QueueMessage):
    try:
        await run_in_threadpool(_publish, queue, message.to_json().encode("utf-8"))
    except (pika.exceptions.AMQPError, OSError) as e:
        log.error(f"Could not publish to queue {queue}: {type(e).__name__}")
        raise BrokerUnavailable(queue) from e
