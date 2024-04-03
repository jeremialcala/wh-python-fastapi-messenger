# -*- coding: utf8 -*-
import json
import logging
import asyncio

import requests
from uuid import uuid4

from inspect import currentframe

from fastapi import Response, status
from mongoengine.errors import OperationError

from classes import ChatbotRequest, ChatBot, ChatbotPhone, Contact, ProfileInfo
from classes import Settings, FacebookRequest, Entry, Changes, Value, Messaging
from constants import APPLICATION_JSON, CONTENT_TYPE, CONTENT_LENGTH

settings = Settings()
log = logging.getLogger(settings.environment)


async def ctr_get_contact_from_facebook_id(fb_id: str, _bot: ChatBot) -> Contact:
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Connecting to Facebook to get user profile: {fb_id}")
    log.info(ctr_identify_fb_contact.__name__)
    try:
        url = settings.facebook_graph_url.format(fb_id=fb_id, ACCESSTOKEN=_bot.facebookToken)
        resp = requests.get(url)
        log.debug(resp.text)
        if resp.status_code != status.HTTP_200_OK:
            log.error(f"There is an error on this request: {resp.text}")
            raise Exception(resp.status_code, resp.text)

        _profile = ProfileInfo(**resp.json())
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return await Contact.generate_contact_from_fb(_bot.uuid, _profile)

    except Exception as e:
        log.error(e.__str__())


async def ctr_identify_fb_contact(fbId: str, _bot: ChatBot) -> Contact:
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Identifying this contact {fbId}")
    contact = None
    try:
        contact = await Contact.get_contact_by_fb_id(fbId, _bot.uuid)
        log.info(contact)
    except IndexError as e:
        log.error(e.__str__())
        contact = await ctr_get_contact_from_facebook_id(fb_id=fbId, _bot=_bot)
        contact.save()

    except Exception as e:
        log.error(e.__str__())
        raise Exception(e.args)

    finally:
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return contact


