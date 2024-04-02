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


class QueueMessage(Document):
    _uuid = UUIDField(required=True, unique=True, default=uuid4())
    eventId = UUIDField(required=True)
    endpoint = StringField()
    operation = StringField()
    jwe_body = StringField()
    createdAt = DateTimeField(required=True, default=datetime.now())
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now())

    

