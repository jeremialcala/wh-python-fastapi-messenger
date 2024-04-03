# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from uuid import uuid4, UUID
from mongoengine import *
from enums import Status
from .tool_settings import Settings
from .entity_credentials import Credentials
from .entity_chatbot import ChatBot
from .dto_facebook_info import ProfileInfo

settings = Settings()
log = logging.getLogger(settings.environment)
connect(
    db=settings.db_name,
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host
)


class Contact(Document):
    _uuid = UUIDField(required=True, unique=True, default=uuid4())
    botId = UUIDField(required=True)
    firstName = StringField()
    lastName = StringField()
    profilePic = URLField()
    fbId = StringField()
    waId = StringField()
    createdAt = DateTimeField(required=True, default=datetime.now())
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now())

    @staticmethod
    async def get_contact_by_wa_id(waId: str, botId: UUID):
        return [contact for contact in Contact.objects(waId=waId, botId=botId)][-1]

    @staticmethod
    async def get_contact_by_fb_id(fbId: str, botId: UUID):
        return [contact for contact in Contact.objects(fbId=fbId, botId=botId)][-1]

    @staticmethod
    async def update_whatsapp_id(wa_id: str, _uuid: str, bot_id: str):
        (Contact.objects(_uuid=_uuid, bot_id=bot_id).update_ones(set__waId=wa_id))

    @staticmethod
    async def generate_contact_from_fb(botId: str, fb_info: ProfileInfo):
        log.info(f"Creating a new contact from this profile: {fb_info.json()}")
        return Contact(
            _uuid=uuid4(),
            botId=botId,
            firstName=fb_info.first_name,
            lastName=fb_info.last_name,
            profilePic=fb_info.profile_pic,
            fbId=fb_info.id
        )


