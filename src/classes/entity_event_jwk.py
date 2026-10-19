# -*- coding: utf-8 -*-
import logging
from mongoengine import *
from .tool_settings import Settings


settings = Settings()
log = logging.getLogger(settings.environment)
connect(
    db=settings.db_name,
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host
)


class EventJwk(Document):
    eventId = UUIDField(required=True)
    jwkId = UUIDField(required=True)
