# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings
from .dto_facebook_message import Message
from .dto_facebook_metadata import Metadata
from .dto_facebook_contact import Contact

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Value(BaseModel):
    messaging_product: str = Field(default="whatsapp", examples=["whatsapp"])
    metadata: Metadata = Field(default=Metadata())
    contacts: list = Field(default=[Contact() for _ in range(1)])
    messages: list = Field(default=[Message() for _ in range(1)])

    @property
    def message(self):
        return self.messages[-1]
