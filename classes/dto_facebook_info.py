# -*- coding: utf-8 -*-
import logging

from faker import Faker
from pydantic import BaseModel, Field

from .tool_settings import Settings


fk = Faker()
settings = Settings()
log = logging.getLogger(settings.environment)


class ProfileInfo(BaseModel):
    id: str = Field(default="6513749358714062")
    first_name: str = Field(default="Jeremi J")
    last_name: str = Field(default="Alcala M")
    profile_pic: str = Field(default="https://platform-lookaside.fbsbx.com/platform/profilepic/?eai=AXGEjoaR38N4VULkLaXuu5X0pp02bHHw3InAOyt-yeojuSpNj92H2n9Co1fQ9Ts33jEQXrdBmSDI1g&psid=6513749358714062&width=1024&ext=1714571050&hash=Afq64DcApuBsCpFu8j-3wmU90Ky_TZvjEjNBMZTFbyU0VQ")

