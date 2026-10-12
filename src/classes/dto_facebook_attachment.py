# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings
from .dto_facebook_payload import Payload
fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Attachment(BaseModel):
    title: str | None = Field(default=None)
    type: str | None = Field(default="image")
    payload: Payload | None = Field(default=Payload())
