# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings

from .dto_facebook_sender import Sender
from .dto_facebook_postback import Postback
from .dto_facebook_message import Message

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Messaging(BaseModel):
    sender: Sender = Field(examples=[Sender()])
    recipient: Sender = Field(examples=[Sender()])
    timestamp: str
    read: str
    postback: Postback
    delivery: str
    message: Message


