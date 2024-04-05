# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4, UUID

from jwcrypto import jwk, jwe
from jwcrypto.common import json_encode, json_decode

from classes import Settings

settings = Settings()
log = logging.getLogger(settings.environment)

def get_private_key_pem(_uuid: str):
    with open(settings.private_key_filename.format(UUID=_uuid), "r") as key:
        pem_data = key.read()
        key.close()

    return pem_data


def get_private_key(_uuid):
    return jwk.JWK.from_pem(data=get_private_key_pem(_uuid).encode("utf-8"))


def get_public_key(_uuid):
    public_key = jwk.JWK()
    public_key.import_key(**json_decode(get_private_key(_uuid).export_public()))
    return public_key
