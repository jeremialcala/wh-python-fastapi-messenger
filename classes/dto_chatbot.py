# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class ChatbotRequest(BaseModel):
    name: str = Field(examples=[fk.name() for _ in range(5)])
    role: str = Field(examples=["Sales Assistant", "Office Assistant", "Tech Support"])
    description: str = Field(examples=["Please ensure that your responses are socially unbiased and positive in nature."])
    tone: str = Field(examples=["helpful", "respectful", "honest"])
