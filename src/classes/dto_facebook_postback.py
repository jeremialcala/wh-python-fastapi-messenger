# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings
from .dto_facebook_payload import Payload

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Postback(BaseModel):
    payload: Payload = Field(default=Payload())
    title: str = Field(default="Demo")
