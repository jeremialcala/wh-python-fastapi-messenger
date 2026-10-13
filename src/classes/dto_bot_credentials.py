# -*- coding: utf-8 -*-
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BotCredentialsRequest(BaseModel):
    """
        The Meta credentials of a chatbot. Each one that is sent replaces the stored one; the ones left out stay
        as they are. They are stored encrypted and no endpoint returns them.
    """
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    facebookToken: str | None = Field(default=None, min_length=1, max_length=2048)
    whatsappToken: str | None = Field(default=None, min_length=1, max_length=2048)
    appSecret: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def at_least_one(self):
        if self.facebookToken is None and self.whatsappToken is None and self.appSecret is None:
            raise ValueError("Send at least one credential")
        return self
