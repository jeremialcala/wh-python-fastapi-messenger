# -*- coding: utf8 -*-
import json
import logging
import asyncio

import requests
from uuid import uuid4

from fastapi import Response, status
from mongoengine.errors import OperationError

from classes import ChatbotRequest, ChatBot, ChatbotPhone, Contact, ProfileInfo
from classes import Settings, FacebookRequest, Entry, Changes, Value, Messaging
from constants import APPLICATION_JSON, CONTENT_TYPE, CONTENT_LENGTH

settings = Settings()
log = logging.getLogger(settings.environment)


async def ctr_get_contact_from_facebook_id(fb_id: str, _bot: ChatBot) -> Contact:
    url = settings.facebook_graph_url.format(fb_id=fb_id, ACCESSTOKEN=_bot.facebookToken)
    resp = requests.get(url)
    if resp.status_code != status.HTTP_200_OK:
        log.error(f"There is an error on this request: {resp.text}")
        raise Exception(resp.status_code, resp.text)

    _profile = ProfileInfo(**resp.json())
    return await Contact.generate_contact_from_fb(_bot.uuid, _profile)


async def ctr_identify_fb_contact(fbId: str, _bot: ChatBot) -> Contact:
    log.info(f"Identifying this contact {fbId}")
    contact = None
    try:
        contact = Contact.get_contact_by_fb_id(fbId, _bot.uuid)
    except ValueError as e:
        log.error(e.__str__())
        contact = await ctr_get_contact_from_facebook_id(fb_id=fbId, _bot=_bot)
        contact.save()
    finally:
        return contact


