# -*- coding: utf-8 -*-
import logging
import json
from jwcrypto import jwk, jwt
from datetime import datetime
from uuid import uuid4, UUID
from mongoengine import *
from enums import Status
from inspect import currentframe
from .tool_settings import Settings


settings = Settings()
log = logging.getLogger(settings.environment)
connect(
    db=settings.db_name,
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host
)

"""
    This Object generates credentials for token generation
    
"""


class Credentials(Document):
    uuid = UUIDField(required=True, unique=True, default=uuid4())
    _header = DictField(required=True, default={"alg": "HS256"})
    _claims = DictField()
    _key = StringField(default=jwk.JWK(generate='oct', size=256).export_symmetric())
    jwt = StringField()

    @property
    def key(self) -> jwk.JWK:
        return jwk.JWK().from_json(self._key)

    def set_header(self, alg: str = "HS256"):
        self._header = {"alg": alg}

    def set_claims(self, claim):
        log.info(f"executing: {currentframe().f_code.co_name}")
        self._claims = {"info": claim}

    def set_jwt(self):
        self.jwt = jwt.JWT(header=self._header, claims=self._claims)
