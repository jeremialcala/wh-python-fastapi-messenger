# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from uuid import uuid4
from mongoengine import *
from enums import Status
from .tool_settings import Settings
from .tool_database import connect_database

settings = Settings()
log = logging.getLogger(settings.environment)
connect_database(settings)


class Rule(Document):
    uuid = UUIDField(required=True, unique=True, default=uuid4)
    clientId = UUIDField(required=True)
    botId = UUIDField(required=True)
    rule = StringField(required=True)
    createdAt = DateTimeField(required=True, default=datetime.now)
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now)
