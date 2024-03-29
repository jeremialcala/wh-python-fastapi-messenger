# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from uuid import uuid4, UUID
from mongoengine import *
from enums import Status
from .tool_settings import Settings
from .entity_credentials import Credentials


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
    role = StringField(required=True)
    description = StringField(required=True)
    tone = StringField(required=True)
    verifyToken = StringField()
    createdAt = DateTimeField(required=True, default=datetime.now())
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now())

    def chatbot_info(self) -> dict:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "rol": self.role,
            "verifyToken": self.verifyToken
        }

    def generate_verify_token(self):
        _cred = Credentials()
        _cred.set_claims(claim=self.name)
        _cred.set_jwt()
        _cred.jwt.make_signed_token(_cred.key)
        _cred.save()
        self.verifyToken = _cred.jwt.serialize()

    @staticmethod
    async def get_chatbot_by_uuid(_uuid: str):
        return [chatbot for chatbot in ChatBot.objects(uuid=UUID(_uuid))][-1]
