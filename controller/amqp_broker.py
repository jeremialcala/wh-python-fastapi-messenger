# -*- coding: utf8 -*-
import logging

import pika

from classes import Settings, QueueMessage

settings = Settings()
log = logging.getLogger(settings.environment)


async def send_message_to_queue(queue: str, message: QueueMessage):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.qms_server,
            credentials=pika.credentials.PlainCredentials(
                username=settings.qms_user,
                password=settings.qms_password
            ),
        )
    )
    channel = connection.channel()
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange='',
                          routing_key=queue,
                          body=message.to_json().encode("utf-8"))
    connection.close()
