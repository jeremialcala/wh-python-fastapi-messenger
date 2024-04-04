# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings
from .dto_facebook_message import Message
from .dto_facebook_metadata import Metadata
from .dto_facebook_contact import Contact

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class MessageBody(BaseModel):
    botId: str
    type: str
    contact: dict
    message: dict
