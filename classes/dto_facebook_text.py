# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings


fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Text(BaseModel):
    preview_url: bool | None = Field(default=None)
    body: str = Field(default="Hello World")
