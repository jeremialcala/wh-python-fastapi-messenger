# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings
from .dto_facebook_profile import Profile

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Contact(BaseModel):
    profile: dict | Profile = Field(default=Profile())
    wa_id: str = Field(default="584127733522")
