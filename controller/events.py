# -*- coding: utf8 -*-
import logging
import asyncio
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
        log.info(f"Creating the Event {event.uuid}")
        _event = Event(**event.model_dump())
        _event.save()
        asyncio.ensure_future(Jwk().create_key_for_event(event.uuid))

    except Exception as e:
        log.error(e.__str__())


