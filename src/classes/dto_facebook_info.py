# -*- coding: utf-8 -*-
from pydantic import BaseModel


class ProfileInfo(BaseModel):
    """
        What the Graph API gave of a Messenger profile. What it left out stays empty: a default here would be stored
        as that person's data.
    """
    first_name: str | None = None
    last_name: str | None = None
    profile_pic: str | None = None
