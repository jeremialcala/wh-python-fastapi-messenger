# -*- coding: utf8 -*-
import json
import logging
from asyncio import ensure_future
import requests
from uuid import uuid4, UUID

from inspect import currentframe

from fastapi import Response, status
from mongoengine.errors import OperationError

from classes import ChatbotRequest, ChatBot, ChatbotPhone, Contact, ProfileInfo
from classes import Settings, FacebookRequest, Entry, Changes, Value, Messaging
from constants import APPLICATION_JSON, CONTENT_TYPE, CONTENT_LENGTH
from enums import Status
from .events import ctr_notify_action

settings = Settings()
log = logging.getLogger(settings.environment)


async def ctr_get_contact_from_facebook_id(fb_id: str, _bot: ChatBot, eventId: str=None) -> Contact:
    """

    :param fb_id:
    :param _bot:
    :param eventId:
    :return:
    """
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Connecting to Facebook to get user profile: {fb_id}")
    log.info(ctr_identify_fb_contact.__name__)
    _action = uuid4()
    if eventId is not None:
        ensure_future(ctr_notify_action(
            _uuid=_action,
            event_id=UUID(eventId),
            operation="",
            method=currentframe().f_code.co_name
        ))
    try:
        url = settings.facebook_graph_url.format(fb_id=fb_id, ACCESSTOKEN=_bot.facebookToken)
        resp = requests.get(url)
        log.debug(resp.text)
        if resp.status_code != status.HTTP_200_OK:
            log.error(f"There is an error on this request: {resp.text}")
            raise Exception(resp.status_code, resp.text)

        _profile = ProfileInfo(**resp.json())
        log.info(f"Ending: {currentframe().f_code.co_name}")
        if eventId is not None:
            ensure_future(ctr_notify_action(
                _uuid=_action,
                event_id=UUID(eventId),
                operation="",
                method=currentframe().f_code.co_name,
                description="This process completed the way we needed",
                status=Status.COM.value
            ))
        return await Contact.generate_contact_from_fb(_bot.uuid, _profile)

    except Exception as e:
        if eventId is not None:
            ensure_future(ctr_notify_action(
                _uuid=_action,
                event_id=UUID(eventId),
                operation="",
                method=currentframe().f_code.co_name,
                description=e.__str__(),
                status=Status.ERR.value
            ))
        log.error(e.__str__())


async def ctr_identify_fb_contact(fbId: str, _bot: ChatBot, eventId: str=None) -> Contact:
    """

    :param fbId:
    :param _bot:
    :param eventId:
    :return:
    """
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Identifying this contact {fbId}")
    contact = None
    _action = uuid4()
    if eventId is not None:
        ensure_future(ctr_notify_action(
            _uuid=_action,
            event_id=UUID(eventId),
            operation="",
            method=currentframe().f_code.co_name
        ))
    try:
        contact = await Contact.get_contact_by_fb_id(fbId, _bot.uuid)
        log.info(contact)
    except IndexError as e:
        log.error(e.__str__())
        contact = await ctr_get_contact_from_facebook_id(fb_id=fbId, _bot=_bot)
        contact.save()

    except Exception as e:
        log.error(e.__str__())
        if eventId is not None:
            ensure_future(ctr_notify_action(
                _uuid=_action,
                event_id=UUID(eventId),
                operation="",
                method=currentframe().f_code.co_name,
                description=e.__str__(),
                status=Status.ERR.value
            ))

        raise Exception(e.args)

    finally:
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
        return contact


async def ctr_identify_contact_by_wa_id(wa_id: str, name: str, _bot: ChatBot, eventId: str = None):
    """

    :param wa_id:
    :param name:
    :param _bot:
    :param eventId
    :return:
    """
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Identifying this contact {wa_id}")

    _action = uuid4()
    if eventId is not None:
        ensure_future(ctr_notify_action(
            _uuid=_action,
            event_id=UUID(eventId),
            operation="",
            method=currentframe().f_code.co_name
        ))

    contact = None
    try:
        contact = await Contact.get_contact_by_wa_id(wa_id, _bot.uuid)
        log.info(contact)
    except IndexError as e:
        log.error(e.__str__())
        contact = Contact(_uuid=uuid4(), botId=_bot.uuid, firstName=name, waId=wa_id)
        contact.save()

    except Exception as e:
        log.error(e.__str__())
        if eventId is not None:
            ensure_future(ctr_notify_action(
                _uuid=_action,
                event_id=UUID(eventId),
                operation="",
                method=currentframe().f_code.co_name,
                description=e.__str__(),
                status=Status.ERR.value
            ))
        raise Exception(e.args)

    finally:
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
        return contact

