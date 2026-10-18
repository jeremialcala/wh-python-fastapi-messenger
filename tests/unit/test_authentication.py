# -*- coding: utf-8 -*-
"""
    Authentication of everything that is not the webhook: a JWT signed by the client inside a JWE encrypted to the
    gateway. A token built the documented way gets in; every way of forging, altering or replaying one gets the
    same 401. The tokens are real, the clients are registered in the in-memory database, and the requests go
    through the application.
"""
import json
import time
from datetime import timezone
from uuid import uuid4

import mongoengine
import pytest
from fastapi.testclient import TestClient
from jwcrypto import jwe, jwk, jws

import app as app_module
from auth import gateway_keys, tokens
from auth.client import new_signing_key
from classes import Client, SeenToken
from conftest import GATEWAY_AUDIENCE, GATEWAY_KEYS_FILE
from enums import Status
from repository import find_signer

GATEWAY_KEY = gateway_keys.GatewayKeys.load(GATEWAY_KEYS_FILE).public_set()["keys"][0]


@pytest.fixture
def http():
    return TestClient(app_module.app)


@pytest.fixture
def caller(register):
    return register("acme")


def status_of(http, token) -> int:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return http.get("/keys", headers=headers).status_code


def forge(caller, sign_with: dict | None = None, signature: str = "ES256", jws_header: dict | None = None,
          encrypt_to: dict | None = None, jwe_header: dict | None = None, inner: str | None = None, **claims) -> str:
    """A token like the real one, with whatever a test wants changed."""
    now = int(time.time())
    body = {"iss": str(caller.client_id), "aud": GATEWAY_AUDIENCE, "iat": now, "exp": now + 60, "jti": str(uuid4())}
    body.update({name: value(now) if callable(value) else value for name, value in claims.items()})
    body = {name: value for name, value in body.items() if value is not None}
    if inner is None:
        key = jwk.JWK(**(sign_with or caller.key))
        signed = jws.JWS(json.dumps(body).encode())
        signed.allowed_algs = [signature]
        signed.add_signature(key, alg=signature,
                             protected={"alg": signature, "typ": "JWT", "kid": caller.kid, **(jws_header or {})})
        inner = signed.serialize(compact=True)
    target = encrypt_to or GATEWAY_KEY
    protected = {"alg": "RSA-OAEP-256", "enc": "A256CBC-HS512", "cty": "JWT", "kid": target.get("kid", "none"),
                 **(jwe_header or {})}
    envelope = jwe.JWE(inner.encode(), protected=protected,
                       algs=["RSA-OAEP-256", "RSA-OAEP", "A256CBC-HS512", "A256GCM", "dir"])
    envelope.add_recipient(jwk.JWK(**target))
    return envelope.serialize(compact=True)


# --- A good token ------------------------------------------------------------------------------------------------

def test_a_token_built_the_documented_way_gets_in(http, caller):
    response = http.get("/keys", headers=caller.auth)

    assert response.status_code == 200
    assert response.json()["data"]["uuid"] == str(caller.client_id)


def test_the_forged_token_of_these_tests_is_valid_when_nothing_is_changed(http, caller):
    """Without this, every rejection below could be the helper's fault."""
    assert status_of(http, forge(caller)) == 200


def test_the_audience_may_be_one_of_several(http, caller):
    assert status_of(http, forge(caller, aud=["https://other.test", GATEWAY_AUDIENCE])) == 200


def test_a_clock_slightly_off_is_tolerated(http, caller):
    now = int(time.time())

    assert status_of(http, forge(caller, iat=now + 20, exp=now + 80)) == 200
    assert status_of(http, forge(caller, iat=now - 80, exp=now - 20)) == 200


# --- No token, or not a token --------------------------------------------------------------------------------------

@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": ""},
    {"Authorization": "Bearer"},
    {"Authorization": "Bearer not-a-token"},
    {"Authorization": "Bearer a.b.c.d.e"},
    {"Authorization": "Basic dXNlcjpwYXNz"},
    {"X-API-Key": "test-admin-api-key-0123456789abcdef"},
], ids=["nothing", "empty", "no value", "garbage", "five parts of nothing", "another scheme", "the old admin key"])
def test_a_request_without_a_token_is_rejected(http, headers):
    response = http.get("/keys", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "HTTP_401_UNAUTHORIZED"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_an_oversized_token_is_rejected_before_it_is_parsed(http, caller):
    assert status_of(http, forge(caller, padding="x" * 9000)) == 401


# --- The envelope ----------------------------------------------------------------------------------------------------

def test_a_token_encrypted_to_another_key_is_rejected(http, caller):
    another = gateway_keys.public_part(gateway_keys.new_key())

    assert status_of(http, forge(caller, encrypt_to=another)) == 401
    # Not even when it claims to be for the gateway's key.
    assert status_of(http, forge(caller, encrypt_to=another, jwe_header={"kid": GATEWAY_KEY["kid"]})) == 401


@pytest.mark.parametrize("header", [
    {"alg": "RSA-OAEP"},
    {"enc": "A256GCM"},
    {"cty": "text/plain"},
    {"cty": None},
    {"kid": "another-kid"},
    {"kid": None},
], ids=["other key algorithm", "other content algorithm", "not a JWT inside", "no cty", "unknown kid", "no kid"])
def test_an_envelope_that_is_not_exactly_as_agreed_is_rejected(http, caller, header):
    changed = {name: value for name, value in header.items() if value is not None}
    token = forge(caller, jwe_header=changed)
    if None in header.values():
        # jwcrypto always writes what it was given, so the member is taken out of the protected header by hand:
        # the result no longer authenticates, and it has to be rejected for that or for the missing member.
        token = forge(caller, jwe_header={name: "" for name in header})

    assert status_of(http, token) == 401


def test_a_symmetric_envelope_is_rejected(http, caller):
    shared = jwk.JWK.generate(kty="oct", size=512)
    envelope = jwe.JWE(b"x", protected={"alg": "dir", "enc": "A256CBC-HS512", "cty": "JWT", "kid": GATEWAY_KEY["kid"]})
    envelope.add_recipient(shared)

    assert status_of(http, envelope.serialize(compact=True)) == 401


def test_an_envelope_with_something_else_inside_is_rejected(http, caller):
    assert status_of(http, forge(caller, inner="this is not a JWT")) == 401
    assert status_of(http, forge(caller, inner="a.b.c")) == 401


# --- The signature ---------------------------------------------------------------------------------------------------

def test_a_token_signed_with_another_key_is_rejected(http, caller):
    assert status_of(http, forge(caller, sign_with=new_signing_key())) == 401


def test_a_token_signed_by_one_client_in_the_name_of_another_is_rejected(http, caller, register):
    other = register("globex")

    assert status_of(http, forge(caller, iss=str(other.client_id))) == 401
    assert status_of(http, forge(caller, iss=str(other.client_id), jws_header={"kid": other.kid})) == 401


def test_an_unsigned_token_is_rejected(http, caller):
    header = jws.base64url_encode(json.dumps({"alg": "none", "typ": "JWT", "kid": caller.kid}))
    now = int(time.time())
    body = jws.base64url_encode(json.dumps({"iss": str(caller.client_id), "aud": GATEWAY_AUDIENCE, "iat": now,
                                            "exp": now + 60, "jti": "unsigned"}))

    assert status_of(http, forge(caller, inner=f"{header}.{body}.")) == 401


def test_a_token_signed_with_the_public_key_as_a_shared_secret_is_rejected(http, caller):
    """The classic confusion: the verifier is handed an HMAC made with the key it holds, which is public."""
    public = {name: caller.key[name] for name in ("kty", "crv", "x", "y")}
    secret = jwk.JWK(kty="oct", k=jws.base64url_encode(json.dumps(public)))

    assert status_of(http, forge(caller, sign_with=json.loads(secret.export()), signature="HS256")) == 401


def test_another_signature_algorithm_is_rejected(http, caller):
    other_curve = json.loads(jwk.JWK.generate(kty="EC", crv="P-384").export_private())

    assert status_of(http, forge(caller, sign_with=other_curve, signature="ES384")) == 401


@pytest.mark.parametrize("header", [{"kid": "unknown"}, {"kid": ""}, {"kid": 7}],
                         ids=["unknown kid", "empty kid", "kid that is not text"])
def test_a_token_that_does_not_name_a_registered_key_is_rejected(http, caller, header):
    assert status_of(http, forge(caller, jws_header=header)) == 401


@pytest.mark.parametrize("issuer", [None, "", "acme", str(uuid4()), 7, ["a"]],
                         ids=["missing", "empty", "a name", "unknown client", "a number", "a list"])
def test_a_token_from_nobody_known_is_rejected(http, caller, issuer):
    assert status_of(http, forge(caller, iss=issuer)) == 401


def test_a_tampered_token_is_rejected(http, caller):
    token = caller.token()
    head, key, iv, text, tag = token.split(".")
    flipped = text[:-2] + ("AA" if text[-2:] != "AA" else "BB")

    assert status_of(http, ".".join([head, key, iv, flipped, tag])) == 401


# --- The claims ------------------------------------------------------------------------------------------------------

def at(offset: int):
    """A moment relative to when the token is forged, not to when this file was read: a slow run cannot change it."""
    return lambda now: now + offset


@pytest.mark.parametrize("claims", [
    {"aud": "https://other.test"},
    {"aud": ["https://other.test"]},
    {"aud": None},
    {"exp": None},
    {"iat": None},
    {"iat": "now", "exp": "later"},
    {"iat": True, "exp": True},
    {"iat": at(0), "exp": at(61)},
    {"iat": at(0), "exp": at(3600)},
    {"iat": at(0), "exp": at(0)},
    {"iat": at(0), "exp": at(-10)},
    {"iat": at(-120), "exp": at(-60)},
    {"iat": at(120), "exp": at(180)},
    {"jti": None},
    {"jti": ""},
    {"jti": 7},
    {"jti": "x" * 129},
], ids=["another audience", "another audience in a list", "no audience", "no exp", "no iat", "dates that are text",
        "dates that are booleans", "one second too long", "an hour", "no lifetime", "expires before it is issued",
        "expired", "issued in the future", "no jti", "empty jti", "jti that is not text", "jti too long"])
def test_a_token_with_wrong_claims_is_rejected(http, caller, claims):
    assert status_of(http, forge(caller, **claims)) == 401


# --- Each check is the one that rejects --------------------------------------------------------------------------

OTHER_GATEWAY = gateway_keys.public_part(gateway_keys.new_key())
OTHER_CURVE = json.loads(jwk.JWK.generate(kty="EC", crv="P-384").export_private())

REASONS = {
    "not encrypted to a key of this gateway": {"encrypt_to": OTHER_GATEWAY},
    "the JWE does not open": {"encrypt_to": OTHER_GATEWAY, "jwe_header": {"kid": GATEWAY_KEY["kid"]}},
    "JWE algorithm not allowed": {"jwe_header": {"enc": "A256GCM"}},
    "the JWE does not declare a JWT inside": {"jwe_header": {"cty": "text/plain"}},
    "malformed JWT": {"inner": "this is not a JWT"},
    "JWT algorithm not allowed": {"sign_with": OTHER_CURVE, "signature": "ES384"},
    "no issuer": {"iss": "acme"},
    "unknown client or key": {"jws_header": {"kid": "unknown"}},
    "bad signature": {"sign_with": new_signing_key()},
    "issued for another audience": {"aud": "https://other.test"},
    "no iat or exp": {"exp": None},
    "lifetime longer than allowed": {"iat": at(0), "exp": at(61)},
    "issued in the future": {"iat": at(120), "exp": at(180)},
    "expired": {"iat": at(-120), "exp": at(-60)},
    "no jti": {"jti": ""},
}


@pytest.mark.parametrize("extra", [False, True], ids=["as it is", "with an issuer outside the signature"])
def test_a_jwt_in_json_form_is_malformed(http, caller, register, extra):
    """
        Found in the dual review of Gate 2: the JSON form was taken, and the issuer was read from bytes the
        signature does not cover. With the key of acme, this says it is acme outside and somebody else inside.
    """
    now = int(time.time())
    claims = {"iss": str(uuid4()) if extra else str(caller.client_id), "aud": GATEWAY_AUDIENCE, "iat": now,
              "exp": now + 60, "jti": str(uuid4())}
    signed = jws.JWS(json.dumps(claims).encode())
    signed.add_signature(jwk.JWK(**caller.key), alg="ES256", protected={"alg": "ES256", "kid": caller.kid})
    inner = json.loads(signed.serialize(compact=False))
    if extra:
        issuer = jws.base64url_encode(json.dumps({"iss": str(caller.client_id)}))
        inner["a"] = f"a.{issuer}.b"
    token = forge(caller, inner=json.dumps(inner))

    with pytest.raises(tokens.InvalidToken) as rejection:
        tokens.verify(token, gateway_keys.GatewayKeys.load(GATEWAY_KEYS_FILE), GATEWAY_AUDIENCE,
                      lambda client_id, kid: (find_signer(client_id, kid) or (None, None))[1], time.time())

    assert str(rejection.value) == "malformed JWT"
    assert status_of(http, token) == 401


@pytest.mark.parametrize("reason", sorted(REASONS))
def test_a_token_is_rejected_for_the_reason_it_should_be(caller, reason):
    """Seen from outside every rejection is the same 401, so this looks at which check turned the token away."""
    def signing_key(client_id, kid):
        found = find_signer(client_id, kid)
        return found[1] if found else None

    with pytest.raises(tokens.InvalidToken) as rejection:
        tokens.verify(forge(caller, **REASONS[reason]), gateway_keys.GatewayKeys.load(GATEWAY_KEYS_FILE),
                      GATEWAY_AUDIENCE, signing_key, time.time())

    assert str(rejection.value) == reason


# --- A single use ----------------------------------------------------------------------------------------------------

def test_a_token_is_valid_once(http, caller):
    token = caller.token()

    assert [status_of(http, token), status_of(http, token), status_of(http, token)] == [200, 401, 401]


def test_two_clients_may_use_the_same_jti(http, caller, register):
    other = register("globex")

    assert status_of(http, forge(caller, jti="same")) == 200
    assert status_of(http, forge(other, sign_with=other.key, jws_header={"kid": other.kid}, jti="same")) == 200
    assert status_of(http, forge(caller, jti="same")) == 401


def test_a_rejected_token_does_not_burn_the_jti(http, caller):
    """Otherwise anyone could invalidate a client's next token by sending the jti first, unsigned."""
    assert status_of(http, forge(caller, sign_with=new_signing_key(), jti="mine")) == 401
    assert status_of(http, forge(caller, aud="https://other.test", jti="mine")) == 401
    assert SeenToken.objects.count() == 0
    assert status_of(http, forge(caller, jti="mine")) == 200


def test_a_used_token_is_remembered_until_it_could_not_be_presented_again(http, caller):
    now = int(time.time())
    status_of(http, forge(caller, iat=now, exp=now + 60, jti="kept"))

    seen = SeenToken.objects.get()
    assert (seen.key, seen.clientId) == (f"{caller.client_id}:kept", caller.client_id)
    # exp plus the clock tolerance. MongoDB deletes the entry by itself after that.
    assert abs(seen.expiresAt.replace(tzinfo=timezone.utc).timestamp() - (now + 90)) < 2
    assert {"fields": ["expiresAt"], "expireAfterSeconds": 0} in SeenToken._meta["indexes"]


def test_the_single_use_does_not_depend_on_an_index(http, caller):
    """
        A collection that is dropped while the service runs loses its indexes, and they are not created again
        until it restarts. The single use must hold all the same.
    """
    mongoengine.get_db().drop_collection(SeenToken._get_collection_name())
    token = caller.token()

    assert [status_of(http, token), status_of(http, token)] == [200, 401]


# --- The registry decides ---------------------------------------------------------------------------------------------

def test_a_revoked_key_stops_working_at_once(http, caller, operator):
    assert status_of(http, caller.token()) == 200

    revoked = http.delete(f"/clients/{caller.client_id}/keys/{caller.kid}", headers=operator.auth)

    assert revoked.status_code == 200
    assert status_of(http, caller.token()) == 401


def test_a_client_that_is_not_active_does_not_get_in(http, caller):
    Client.objects(uuid=caller.client_id).update_one(set__status=Status.LOK.value)

    assert status_of(http, caller.token()) == 401


def test_the_answer_does_not_say_why(http, caller, register):
    """Wrong signature, unknown client, replay: nothing in the answer lets a caller tell them apart."""
    other = register("globex")
    used = caller.token()
    status_of(http, used)
    answers = [http.get("/keys", headers={"Authorization": f"Bearer {token}"}) for token in (
        used,
        forge(caller, sign_with=new_signing_key()),
        forge(caller, iss=str(uuid4())),
        forge(caller, iss=str(other.client_id)),
        forge(caller, aud="https://other.test"),
        "not-a-token",
    )]

    assert {(answer.status_code, answer.text) for answer in answers} == {(401, '{"detail":"HTTP_401_UNAUTHORIZED"}')}


# --- Every route ------------------------------------------------------------------------------------------------------

PUBLIC = {("GET", "/chat/{bot_id}"), ("POST", "/chat/{bot_id}"), ("GET", "/health")}
ROUTES = sorted({(method, route.path) for route in app_module.app.routes if hasattr(route, "methods")
                 and not route.path.startswith(("/docs", "/redoc", "/openapi")) for method in route.methods
                 if method != "HEAD"} - PUBLIC)
PLACEHOLDERS = {"bot_id": str(uuid4()), "intent_id": str(uuid4()), "client_id": str(uuid4()), "kid": "a-kid",
                "contact_id": str(uuid4())}


def test_the_webhook_and_health_routes_are_the_only_ones_without_a_token():
    assert len(ROUTES) == 30


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer not-a-token"}], ids=["no token", "garbage"])
@pytest.mark.parametrize("method,path", ROUTES)
def test_every_other_route_asks_for_a_token(http, method, path, headers):
    response = http.request(method, path.format(**PLACEHOLDERS), headers=headers, json={})

    assert response.status_code == 401


@pytest.mark.parametrize("method,path", ROUTES)
def test_no_route_accepts_a_token_twice(http, caller, method, path):
    token = caller.token()
    http.request(method, path.format(**PLACEHOLDERS), headers={"Authorization": f"Bearer {token}"}, json={})

    again = http.request(method, path.format(**PLACEHOLDERS), headers={"Authorization": f"Bearer {token}"}, json={})

    assert again.status_code == 401
