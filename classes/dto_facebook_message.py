# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings

from .dto_facebook_sender import Sender
from .dto_facebook_postback import Postback

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Message(BaseModel):
    mid: str
    seq: str
    text: str
    attachments: list
    reply_to: Sender
    is_echo: str
    quick_reply: str
    app_id: str
    sticker_id: str


