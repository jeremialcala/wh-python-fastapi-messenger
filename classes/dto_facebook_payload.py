# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings
from .dto_facebook_coordinates import Coordinates

fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class Payload(BaseModel):
    url: str
    coordinates: Coordinates = Field(examples=[Coordinates()])
