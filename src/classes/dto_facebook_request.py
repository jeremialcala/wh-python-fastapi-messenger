# -*- coding: utf-8 -*-
from pydantic import BaseModel, ConfigDict, Field

# Meta sends at most this many updates in one notification.
MAX_ENTRIES = 1000


class FacebookRequest(BaseModel):
    """
        A notification from Meta, as far as the service reads it: the kind of object it is about and its entries.
        Both have to be there, and nothing is filled in for what is missing. Whatever else Meta sends, today or
        tomorrow, is ignored: it adds fields without notice.
    """
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)

    object: str = Field(min_length=1, max_length=64)
    entry: list[dict] = Field(max_length=MAX_ENTRIES)
