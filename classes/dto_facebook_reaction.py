# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings


fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Reaction(BaseModel):
    mid: str = Field(default="m_YlMBNmvf-5qi1CCCs3YkyEnWeyZ33LNYRFdwy38FCi8_R_4r_a-R2g2YcwaCsjE9F2StSIyUwLygXTlPF019NQ")
    action: str = Field(default="react")
    emoji: str = Field(default="❤")
    reaction: str = Field(default="other")
