# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings


fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Profile(BaseModel):
    name: str = Field(default=["Jeremi Alcala"])
