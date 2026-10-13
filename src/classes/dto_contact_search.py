# -*- coding: utf-8 -*-
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContactSearchRequest(BaseModel):
    """
        Who to look for among the contacts of a client: a WhatsApp number or a Messenger id, one of the two.
        It travels in the body, not in the address: an address ends up in logs along the way.
    """
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    # A number however it is written: only its digits count.
    waId: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[0-9+() .-]*[0-9][0-9+() .-]*$")
    fbId: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.waId is None) == (self.fbId is None):
            raise ValueError("Send either waId or fbId")
        return self
