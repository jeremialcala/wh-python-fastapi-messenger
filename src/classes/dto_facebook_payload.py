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
    url: str = Field(default="https://scontent.xx.fbcdn.net/v/t39.1997-6/39178562_1505197616293642_5411344281094848512_n.png?stp=cp0_dst-png&_nc_cat=1&ccb=1-7&_nc_sid=5f2048&_nc_ohc=zS9_372_z1oAX8NNyD1&_nc_ad=z-m&_nc_cid=0&_nc_ht=scontent.xx&oh=00_AfBSkdDE4xiy7_H5olF0DWnBCDdQM_I-lyjjMxPMve9JEQ&oe=660D6A0B")
    coordinates: Coordinates | None = Field(default=None, examples=[Coordinates()])
    sticker_id: float = Field(default=369239263222822)
