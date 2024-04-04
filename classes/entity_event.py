# -*- coding: utf-8 -*-
import logging
from asyncio import ensure_future
from datetime import datetime
from uuid import uuid4, UUID
from mongoengine import *
from enums import Status
from .tool_settings import Settings
from .entity_jwk import Jwk

settings = Settings()
log = logging.getLogger(settings.environment)
connect(
    db=settings.db_name,
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host
)


class Event(Document):
    uuid = UUIDField(required=True, unique=True, default=uuid4())
    resource = StringField()
    operation = StringField()
    origen = StringField()
    result = StringField()
    createdAt = DateTimeField(required=True, default=datetime.now())
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now())

    async def prepare_event(self):
        ensure_future(Jwk.create_key_for_event(self.uuid))
        self.save()

