# -*- coding: utf8 -*-
import json
import logging
import asyncio

import requests
from uuid import uuid4

from fastapi import Response, status
from mongoengine.errors import OperationError

from classes import ChatbotRequest, ChatBot, ChatbotPhone, Contact
from classes import Settings, FacebookRequest, Entry, Changes, Value, Messaging
from constants import APPLICATION_JSON, CONTENT_TYPE, CONTENT_LENGTH
from .facebook import ctr_identify_fb_contact

settings = Settings()
log = logging.getLogger(settings.environment)


async def ctr_process_messages(req: FacebookRequest, _bot_info: str):
    log.info(f"Message received we have a: {req.object}")
    try:
        log.debug(req.json())
        _entry = Entry(**req.entry[-1])
        log.info(f"EntryId: {_entry.id}")

        _bot = await ChatBot().get_chatbot_by_uuid(_uuid=_bot_info)

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

            case "whatsapp_business_account":
                """
                    This will handle WhatsApp Messages.
                """
                log.info(f"Product we received: {_entry.change.value.messaging_product}")
                log.info(_entry.change.value.metadata)
                log.info(f"The name of the sender: {_entry.change.value.contacts[-1]['profile']}")
                log.info(f"this is the message: {_entry.change.value.message}")
                # log.info(f"this is the chatbot information {_bot.chatbot_info()}")
                asyncio.ensure_future(ctr_send_wa_message(_bot, _entry.change.value))

    except Exception as e:
        log.error(e.__str__())


async def ctr_send_wa_message(_bot: ChatBot, msg: Value):
    log.info(f"Sending a message to: {msg.contacts[-1]['profile']}")
    try:
        chatbot_phone = await ChatbotPhone.get_phones_by_environment(
            bot_id=str(_bot.uuid),
            environment=settings.environment
        )
        log.info(chatbot_phone)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {_bot.whatsappToken}'
        }
        url = settings.facebook_whatsapp_message.format(
                version=settings.facebook_graph_version,
                PhoneNumberId=chatbot_phone.phoneId)
        log.info(url)
        data = json.dumps({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": msg.contacts[-1]["wa_id"],
            "type": "text",
            "text": {
                "preview_url": False,
                "body": "this is a new message"
            }
        })
        response = requests.request(
            method="POST",
            headers=headers,
            url=url,
            data=data)
        log.info(response.json())
    except Exception as e:
        log.error(e.__str__())

