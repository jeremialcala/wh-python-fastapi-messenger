# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from uuid import uuid4, UUID
from mongoengine import *
from enums import Status
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
