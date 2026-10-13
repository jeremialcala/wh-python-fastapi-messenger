# -*- coding: utf8 -*-
import logging
from asyncio import ensure_future
from inspect import currentframe
from uuid import uuid4, UUID

from classes import ChatBot
from classes import Settings, FacebookRequest, MessageBody, QueueMessage
from enums import Status
from .events import ctr_notify_action
from crypto.key_service import KeyServiceUnavailable
from .amqp_broker import send_message_to_queue, BrokerUnavailable
from .facebook import ctr_identify_fb_contact, ctr_identify_contact_by_wa_id
from .incoming import WHATSAPP, IncomingMessage, incoming_messages

__all__ = ["ctr_process_messages"]

settings = Settings()
log = logging.getLogger(settings.environment)

# The queue the response engine reads from.
QUEUE = "llm"


async def _contact(message: IncomingMessage, channel: str, _bot: ChatBot, eventId: str = None) -> dict:
    """Finds or stores who wrote the message and returns what the envelope says about them."""
    if channel == WHATSAPP:
        contact = await ctr_identify_contact_by_wa_id(wa_id=message.sender, name=message.name, _bot=_bot,
                                                      eventId=eventId)
        # The number as Meta sent it: the stored contact only holds it encrypted.
        return {"name": contact.firstName, "waId": message.sender}

    contact = await ctr_identify_fb_contact(fbId=message.sender, _bot=_bot)
    return {"name": contact.firstName, "fbId": message.sender}


async def ctr_process_messages(req: FacebookRequest, _bot: ChatBot, eventId: str = None):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Message received we have a: {req.object}")
    try:
        _action = uuid4()
        if eventId is not None:
            ensure_future(ctr_notify_action(
                _uuid=_action,
                event_id=UUID(eventId),
                operation="",
                status=Status.ACT.value,
                method=currentframe().f_code.co_name
            ))

        incoming = incoming_messages(req.object, req.entry)
        log.info(f"Messages to queue from this notification: {len(incoming)}")

        # One envelope per message: the identifier Meta gave it is what the response engine deduplicates by.
        for message in incoming:
            body = MessageBody(
                botId=str(_bot.uuid),
                type=req.object,
                contact=await _contact(message, req.object, _bot, eventId),
                message=message.content
            )
            q_message = QueueMessage(
                eventId=eventId,
                messageId=message.message_id,
                jwe_body=body.__dict__
            )
            # Awaited on purpose: Meta must not get a 200 for a message the broker never took.
            await send_message_to_queue(queue=QUEUE, message=q_message)

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
    except (BrokerUnavailable, KeyServiceUnavailable):
        raise
    except Exception as e:
        log.error(e.__str__())
