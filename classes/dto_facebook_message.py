# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings

from .dto_facebook_text import Text
from .dto_facebook_attachment import Attachment


fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Message(BaseModel):
    from_: str = Field(default="584127733522")
    id: str | None = Field(default="wamid.HBgMNTg0MTI3NzMzNTIyFQIAEhgUM0FCNEMzRDdFQzQ1MTVBQjQzODIA")
    mid: str | None = Field(default=None, examples=["m_xx-TwgSDCfGJkjWXROtB0UnWeyZ33LNYRFdwy38FCi_8gZ8-Xx0nrYDUKGzN6f5KZ5o20tOiRYic0EV08jJGTQ"])
    attachment: Attachment | None = Field(default=None, examples=[Attachment() for _ in range(5)])
    timestamp: str = Field(default="1711804166")
    text: Text | str = Field(default=Text())
    type: str = Field(default="text")
