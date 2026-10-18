# -*- coding: utf8 -*-
import logging
from asyncio import ensure_future
from collections import Counter
from inspect import currentframe
from uuid import uuid4, UUID

from classes import ChatBot
from classes import Settings, FacebookRequest, MessageBody, QueueMessage
from enums import Status
from repository import database_failed
from utils import describe
from .events import ctr_notify_action
from crypto.key_service import KeyServiceUnavailable
from .amqp_broker import send_message_to_queue, BrokerUnavailable
from .facebook import ctr_identify_fb_contact, ctr_identify_contact_by_wa_id
from .incoming import READERS, WHATSAPP, IncomingMessage, incoming_messages

__all__ = ["ctr_process_messages", "DatabaseUnavailable", "RETRY_LATER"]

settings = Settings()
log = logging.getLogger(settings.environment)

# The queue the response engine reads from.
QUEUE = "llm"


class DatabaseUnavailable(Exception):
    """The database did not do its part while a notification was being processed."""


# What Meta is asked to deliver again, with a 503: something the service needs is not there, and it will be.
# Nothing else gets anything but a 200: a notification that fails by itself would fail the same way next time,
# and Meta stops delivering to a webhook that keeps failing.
RETRY_LATER = (BrokerUnavailable, KeyServiceUnavailable, DatabaseUnavailable)


async def _contact(message: IncomingMessage, channel: str, _bot: ChatBot, eventId: str = None) -> dict:
    """Finds or stores who wrote the message and returns what the envelope says about them."""
    if channel == WHATSAPP:
        contact = await ctr_identify_contact_by_wa_id(wa_id=message.sender, name=message.name, _bot=_bot,
                                                      eventId=eventId)
        # The number as Meta sent it: the stored contact only holds it encrypted.
        return {"name": contact.firstName, "waId": message.sender}

    contact = await ctr_identify_fb_contact(fbId=message.sender, _bot=_bot)
    return {"name": contact.firstName, "fbId": message.sender}


async def _queue(message: IncomingMessage, channel: str, _bot: ChatBot, eventId: str = None) -> None:
    body = MessageBody(
        botId=str(_bot.uuid),
        clientId=str(_bot.clientId),
        type=channel,
        contact=await _contact(message, channel, _bot, eventId),
        message=message.content
    )
    q_message = QueueMessage(
        eventId=eventId,
        messageId=message.message_id,
        jwe_body=body.__dict__
    )
    # Awaited on purpose: Meta must not get a 200 for a message the broker never took.
    await send_message_to_queue(queue=QUEUE, message=q_message)


async def ctr_process_messages(req: FacebookRequest, _bot: ChatBot, eventId: str = None):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    _action = uuid4()
    if eventId is not None:
        ensure_future(ctr_notify_action(
            _uuid=_action,
            event_id=UUID(eventId),
            operation="",
            status=Status.ACT.value,
            method=currentframe().f_code.co_name
        ))

    if req.object not in READERS:
        log.warning(f"A notification for chatbot {_bot.uuid} is about a kind of object the service does not handle")
        return

    left_out = []
    incoming = incoming_messages(req.object, req.entry, left_out)
    log.info(f"Messages to queue from this notification: {len(incoming)}")
    if left_out:
        log.warning(f"Messages of a notification for chatbot {_bot.uuid} were left out: {dict(Counter(left_out))}")

    # One envelope per message: the identifier Meta gave it is what the response engine deduplicates by.
    for message in incoming:
        try:
            await _queue(message, req.object, _bot, eventId)
        except (BrokerUnavailable, KeyServiceUnavailable):
            raise
        except Exception as e:
            if database_failed(e):
                log.error(f"The database is unavailable: {describe(e)}")
                raise DatabaseUnavailable(type(e).__name__) from None
            # A message that fails by itself would fail again if Meta sent it again, and must not take the rest
            # of the notification with it.
            log.error(f"A message for chatbot {_bot.uuid} could not be processed: {describe(e)}")

    if eventId is not None:
        ensure_future(ctr_notify_action(
            _uuid=_action,
            event_id=UUID(eventId),
            operation="",
            method=currentframe().f_code.co_name,
            description="This process completed the way we needed",
            status=Status.COM.value
        ))

    log.info(f"Ending: {currentframe().f_code.co_name}")
