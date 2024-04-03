# -*- coding: utf8 -*-
import logging
import asyncio
from inspect import currentframe
from classes import EventTransport, Event, Jwk
from classes import Settings

settings = Settings()
log = logging.getLogger(settings.environment)


async def ctr_create_event(event: EventTransport):
    """
        This method only creates events
    :param event: Event DTO that handles the validation for all events.
    :return: Void
    """
    try:
        log.info(f"Starting: {currentframe().f_code.co_name}")
        log.info(f"Creating the Event {event.uuid}")
        _event = Event(**event.model_dump())
        _event.save()
        asyncio.ensure_future(Jwk().create_key_for_event(event.uuid))
        log.info(f"Ending: {currentframe().f_code.co_name}")
    except Exception as e:
        log.error(e.__str__())


