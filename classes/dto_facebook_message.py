# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings

from .dto_facebook_text import Text

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Message(BaseModel):
    from_: str = Field(default="584127733522")
    id: str = Field(default="wamid.HBgMNTg0MTI3NzMzNTIyFQIAEhgUM0FCNEMzRDdFQzQ1MTVBQjQzODIA")
    timestamp: str = Field(default="1711804166")
    text: Text = Field(default=Text())
    type: str = Field(default="text")
