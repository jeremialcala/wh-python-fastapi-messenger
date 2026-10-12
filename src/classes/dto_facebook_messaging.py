# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings

from .dto_facebook_sender import Sender
from .dto_facebook_postback import Postback
from .dto_facebook_message import Message
from .dto_facebook_reaction import Reaction

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Messaging(BaseModel):
    sender: Sender = Field(default=Sender(id="6513749358714062"))
    recipient: Sender = Field(default=Sender(id="101831186329557"))
    timestamp: int = Field(default=1711766575643)
    read: str | None = Field(default=None)
    postback: Postback | None = Field(default=None, examples=[Postback() for _ in range(1)])
    delivery: str | None = Field(default=None)
    message: Message | None = Field(default=Message())
    reaction: Reaction | None = Field(default=None)

