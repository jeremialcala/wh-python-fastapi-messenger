"""
    This controller is in charge of JWE ops
"""
import logging
import json
from jwcrypto import jwe, jwk

from mongoengine import connect
from mongoengine.context_managers import switch_db

from classes import Settings
from constants import KEYS
from utils import (create_dynamic_orm_model, generate_properties,
                   resource_from_model)

logging.getLogger("pymongo").propagate = False
_set = Settings()
connect(
        db=_set.db_name,
        username=_set.db_username,
        password=_set.db_password,
        host=_set.db_host
    )


def retrieve_key(key_uuid: str) -> jwk.JWK:
    """

    :param key_uuid:
    :return:
    """
    _properties = generate_properties(json.loads(_set.entity_jwk))
    _model = create_dynamic_orm_model(
        name="JWK",
        properties=_properties
    )
    with switch_db(_model, KEYS):
        connect(
            db=KEYS,
            alias=KEYS,
            username=_set.db_username,
            password=_set.db_password,
            host=_set.db_host
        )
        data = {"kid": key_uuid}
        _key = resource_from_model(_model, data).to_json()

        return jwk.JWK.from_json(_key)


def encrypt_data(payload: any, public_key: jwk.JWK):
    """

    :param payload:
    :param public_key:
    :return:
    """

    protected_header = {
        "alg": "RSA-OAEP-256",
        "enc": "A256CBC-HS512",
        "typ": "JWE",
        "kid": public_key.thumbprint(),
    }

    token = jwe.JWE(payload.encode('utf-8'), recipient=public_key,   protected=protected_header)

    return token.serialize(compact=True)


def decrypt_data(encrypted_token: str, _key: jwk.JWK):
    """

    :param encrypted_token:
    :param _key:
    :return:
    """
    _jwe = jwe.JWE()
    _jwe.deserialize(encrypted_token, key=_key)

    return _jwe.payload.decode("utf-8")
