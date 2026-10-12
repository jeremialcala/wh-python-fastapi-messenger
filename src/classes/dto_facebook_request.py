# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings
from .dto_facebook_entry import Entry

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class FacebookRequest(BaseModel):
    object: str = Field(default="Page")
    entry: list = Field(default=[Entry()])
