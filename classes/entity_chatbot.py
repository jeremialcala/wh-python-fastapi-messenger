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


class ChatBot(Document):
    uuid = UUIDField(required=True, unique=True, default=uuid4())
    name = StringField(required=True)
    rol = StringField(required=True)
    description = StringField(required=True)
    tone = StringField(required=True)
    createdAt = DateTimeField(required=True, default=datetime.now())
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now())

    async def chatbot_info(self) -> dict:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "rol": self.rol
        }

    @staticmethod
    async def get_chatbot_by_uuid(_uuid: str):
        return [chatbot for chatbot in ChatBot.objects(uuid=UUID(_uuid))]
