# -*- coding: utf-8 -*-
"""
    Settings are read at import time all over the project, so they are pinned here before anything else is imported.
    Environment variables win over config.env: the tests never see real credentials nor reach a real service.
"""
import os
import tempfile

from auth import gateway_keys  # Needs neither settings nor database.

# A key pair for the gateway, made for this run and thrown away with it.
GATEWAY_KEYS_FILE = os.path.join(tempfile.mkdtemp(prefix="gateway-keys-"), "gateway-keys.json")
gateway_keys.write_file(GATEWAY_KEYS_FILE, [gateway_keys.new_key()])
GATEWAY_AUDIENCE = "https://gateway.test"

os.environ.update({
    "GATEWAY_KEYS_FILE": GATEWAY_KEYS_FILE,
    "GATEWAY_AUDIENCE": GATEWAY_AUDIENCE,
    "FACEBOOK_APP_SECRET": "test-app-secret",

    "CLIENT_ID": "test",
    "NATIONAL_ID_URL": "http://127.0.0.1:1",

    "DB_NAME": "test",
    # Nothing listens on port 1, and the connection is replaced by an in-memory database further down: no test
    # can write anywhere real.
    "DB_HOST": "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=500",
    "DB_USERNAME": "test",
    "DB_PASSWORD": "test",

    "SENDER_EMAIL": "test@example.com",
    "SENDER_PASSWORD": "test",
    "GMAIL_SERVER_URL": "127.0.0.1",
    "GMAIL_SERVER_PORT": "1",

    "EXPIRATION_TIME": "60",
    "ACTIVATION_CODE_LENGTH": "6",
    "PASSWORD_LENGTH": "12",

    "QMS_SERVER": "127.0.0.1",
    "QMS_USER": "test",
    "QMS_PASSWORD": "test",

    "KEY_SIZE": "2048",
    "PRIVATE_KEY_FILENAME": "certs/{UUID}_private.pem",
    "PUBLIC_KEY_FILENAME": "certs/{UUID}_public.pem",

    "ENVIRONMENT": "development",
    "VERSION": "0.0.0",

    "VERIFY_TOKEN": "test",

    "FACEBOOK_GRAPH_URL": "http://127.0.0.1:1/{fb_id}?access_token={ACCESSTOKEN}",
    "FACEBOOK_WHATSAPP_MESSAGE": "http://127.0.0.1:1/{version}/{PhoneNumberId}/messages",
    "FACEBOOK_GRAPH_VERSION": "v19.0",
})

# Every entity module connects to MongoDB when it is imported. The connection is swapped here, before any of them
# is, for an in-memory database: the tests run real queries against real documents without a server.
import bson  # noqa: E402
import mongoengine  # noqa: E402
import mongomock  # noqa: E402
import mongomock.collection  # noqa: E402
import pytest  # noqa: E402
from bson.binary import UuidRepresentation  # noqa: E402

# mongoengine stores UUIDs the legacy way unless told otherwise, and that is what the service does today.
LEGACY_UUID = bson.codec_options.CodecOptions(uuid_representation=UuidRepresentation.PYTHON_LEGACY)


class _SizeCheck(bson.BSON):
    """mongomock encodes each document only to measure it, and does it without the codec options of the client."""

    @classmethod
    def encode(cls, document, check_keys=False, codec_options=LEGACY_UUID):
        return super().encode(document, check_keys, LEGACY_UUID)


mongomock.collection.BSON = _SizeCheck

_connect = mongoengine.connect


def _connect_in_memory(*args, **kwargs):
    return _connect(*args, **{**kwargs, "mongo_client_class": mongomock.MongoClient,
                              "uuidRepresentation": "pythonLegacy"})


mongoengine.connect = _connect_in_memory


@pytest.fixture(autouse=True)
def empty_database():
    """
        Each test starts with an empty database. The documents are deleted, not the collections: dropping them
        would take their unique indexes away, and mongoengine only creates those once per process.
    """
    import classes  # noqa: F401  The entities register the connection.

    database = mongoengine.get_db()
    for name in database.list_collection_names():
        database[name].delete_many({})
    yield


class Caller:
    """A registered client and its private key: everything needed to call the service as that client."""

    def __init__(self, client, key: dict):
        self.client_id = client.uuid
        self.key = key
        self.kid = client.signingKeys[0]["kid"]

    def token(self, **changes) -> str:
        from auth.client import build_token

        gateway_key = gateway_keys.GatewayKeys.load(GATEWAY_KEYS_FILE).public_set()["keys"][0]
        return build_token(self.key, self.client_id, GATEWAY_AUDIENCE, gateway_key, **changes)

    @property
    def auth(self) -> dict:
        """A fresh token each time: one is valid for a single request."""
        return {"Authorization": f"Bearer {self.token()}"}


@pytest.fixture
def register():
    """Returns a function that registers a client with a new key pair and gives back its Caller."""
    from auth.client import new_signing_key, public_part
    from auth.client_keys import public_signing_key
    from repository import register_client

    def new_caller(name: str) -> Caller:
        key = new_signing_key()
        return Caller(register_client(name, public_signing_key(public_part(key))), key)

    return new_caller


@pytest.fixture
def operator():
    """The operator, with a signing key registered the way the server command does it."""
    from auth.client import new_signing_key, public_part
    from auth.client_keys import public_signing_key
    from repository import add_signing_key, operator_client

    key = new_signing_key()
    return Caller(add_signing_key(operator_client().uuid, public_signing_key(public_part(key))), key)
