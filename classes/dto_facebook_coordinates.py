# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Coordinates(BaseModel):
    lat: float = Field(default=-0.211572, examples=[-0.211572])
    long: float = Field(default=-78.404918, examples=[-78.404918])
