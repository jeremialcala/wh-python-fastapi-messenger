# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings

from .dto_facebook_messaging import Messaging
from .dto_facebook_changes import Changes

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Entry(BaseModel):
    id: str = Field(default="101831186329557")
    time: float | None = Field(default=1711770006831)
    standby: str | None = Field(default=None)
    messaging: list | None = Field(default=[Messaging() for _ in range(1)])
    changes: list | None = Field(default=[Changes() for _ in range(1)])

    @property
    def change(self):
        return Changes(**self.changes[-1])
