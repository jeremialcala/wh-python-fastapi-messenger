# -*- coding: utf8 -*-
import logging
from asyncio import ensure_future
from inspect import currentframe
from uuid import uuid4, UUID

from classes import ChatBot
from classes import Settings, FacebookRequest, Entry, Messaging, MessageBody, QueueMessage
from enums import Status
from .events import ctr_notify_action
from crypto.key_service import KeyServiceUnavailable
from .amqp_broker import send_message_to_queue, BrokerUnavailable
from .facebook import ctr_identify_fb_contact, ctr_identify_contact_by_wa_id

settings = Settings()
log = logging.getLogger(settings.environment)


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

        log.debug(req.json())
        _entry = Entry(**req.entry[-1])
        log.info(f"EntryId: {_entry.id}")

        body = None

        match req.object:
            case "page":
                """
                    This is the Messenger Handler
                """
                log.info(f"This is a messenger message")
                messaging = Messaging(**_entry.messaging[-1])
                log.info(f"The message is from this sender {messaging.sender.id}")

                contact = await ctr_identify_fb_contact(fbId=messaging.sender.id, _bot=_bot)

                log.debug(f"We found this contact {contact.firstName}")
                log.info(f"{messaging.message}")
                if "is_echo" not in messaging.message:
                    body = MessageBody(
                        botId=str(_bot.uuid),
                        type=req.object,
                        contact={"name": contact.firstName, "fbId": contact.fbId},
                        message=_entry.messaging[-1]
                    )

                """
                    TODO: do we have a conversation with this contact                    
                """

            case "whatsapp_business_account":
                """
                    This will handle WhatsApp Messages.
                """
                log.info(f"Product we received: {_entry.change.value.messaging_product}")
                log.info(_entry.change.value.metadata)
                log.info(f"The name of the sender: {_entry.change.value.contacts[-1]['profile']}")
                log.debug(f"this is the message: {_entry.change.value.message}")

                contact = await ctr_identify_contact_by_wa_id(
                    wa_id=_entry.change.value.contacts[-1]['wa_id'],
                    name=_entry.change.value.contacts[-1]['profile']['name'],
                    _bot=_bot,
                    eventId=eventId
                )

                log.debug(f"We found this contact {contact.firstName}")

                body = MessageBody(
                    botId=str(_bot.uuid),
                    type=req.object,
                    # The number as Meta sent it: the stored contact only holds it encrypted.
                    contact={"name": contact.firstName, "waId": _entry.change.value.contacts[-1]['wa_id']},
                    message=_entry.change.value.__dict__
                )

                log.info(body.json())

        if body is not None:
            q_message = QueueMessage(
                eventId=eventId,
                jwe_body=body.__dict__
            )
            # q_message.set_jwe_body(body)
            # Awaited on purpose: Meta must not get a 200 for a message the broker never took.
            await send_message_to_queue(queue="llm", message=q_message)

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
