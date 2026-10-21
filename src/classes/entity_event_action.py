# -*- coding: utf-8 -*-
import logging
from asyncio import ensure_future
from datetime import datetime
from uuid import uuid4, UUID
from mongoengine import *
from enums import Status
from .tool_settings import Settings
from .tool_database import connect_database

settings = Settings()
log = logging.getLogger(settings.environment)
connect_database(settings)


class EventAction(Document):
    uuid = UUIDField(required=True, unique=True, default=uuid4)
    eventId = UUIDField(required=True)
    operation = StringField()
    method = StringField()
    step = IntField()
    description = StringField()
    totalTime = IntField()
    createdAt = DateTimeField(required=True, default=datetime.now)
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now)

    @staticmethod
    def get_event_action_by_uuid(_uuid: UUID):
        return [action for action in EventAction.objects(uuid=_uuid)][-1]

