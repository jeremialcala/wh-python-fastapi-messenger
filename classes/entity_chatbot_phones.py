# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from uuid import uuid4, UUID
from mongoengine import *
from enums import Status
from .tool_settings import Settings
from .dto_chatbot_phone import ChatbotPhoneRequest

settings = Settings()
log = logging.getLogger(settings.environment)
connect(
    db=settings.db_name,
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host
)


class ChatbotPhone(Document):
    uuid = UUIDField(required=True, unique=True, default=uuid4())
    bot_id = UUIDField(required=True)
    environment = StringField(required=True, default="development")
    phoneNumber = StringField()
    phoneId = StringField()
    createdAt = DateTimeField(required=True, default=datetime.now())
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now())

    @staticmethod
    async def get_phones_by_environment(bot_id: str, environment: str):
        log.info(f"bot_id: {bot_id}")
        return [phone for phone in ChatbotPhone.objects(bot_id=UUID(bot_id))][-1]

    @staticmethod
    async def generate_chatbot_phone_from_request(req: ChatbotPhoneRequest):
        return ChatbotPhone(
            environment=req.environment if req.environment is not None else "development",
            phoneNumber=req.phoneNumber,
            phoneId=req.phoneId
        )
