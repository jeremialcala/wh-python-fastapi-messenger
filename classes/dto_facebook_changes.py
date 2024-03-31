# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings
from .dto_facebook_value import Value
fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Changes(BaseModel):
    value: Value = Field(default=Value())
    field: str = Field(default="messages")
