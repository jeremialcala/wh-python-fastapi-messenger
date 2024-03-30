# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings

from .dto_facebook_messaging import Messaging

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Entry(BaseModel):
    id: str
    time: str
    standby: str
    messaging: Messaging = Field(examples=[[Messaging() for _ in range(1)]])
