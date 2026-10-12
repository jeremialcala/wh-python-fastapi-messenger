# -*- coding: utf-8 -*-
"""
    The client's side of the authentication, as a reference: what a client of the service has to do to call it.
    The tests build their tokens with this, so what is documented for clients is what is verified.
"""
import json
import time
from uuid import uuid4

from jwcrypto import jwe, jwk, jws

from .tokens import CONTENT_ENCRYPTION, KEY_ENCRYPTION, MAX_LIFETIME, SIGNATURE


def new_signing_key() -> dict:
    """A new private P-256 key as a JWK. It never leaves the client: only its public part is registered."""
    key = jwk.JWK.generate(kty="EC", crv="P-256")
    return {**json.loads(key.export_private()), "kid": key.thumbprint()}


def public_part(private: dict) -> dict:
    return {name: private[name] for name in ("kty", "crv", "x", "y") if name in private}


def build_token(signing_key: dict, client_id, audience: str, gateway_key: dict,
                now: float | None = None, lifetime: int = MAX_LIFETIME) -> str:
    """
        A token for one request: sign first, then encrypt. `signing_key` is the client's private JWK and
        `gateway_key` one of the gateway's public ones.
    """
    issued = int(time.time() if now is None else now)
    claims = {"iss": str(client_id), "aud": audience, "iat": issued, "exp": issued + lifetime, "jti": str(uuid4())}

    signed = jws.JWS(json.dumps(claims).encode())
    signed.add_signature(jwk.JWK(**signing_key), alg=SIGNATURE,
                         protected={"alg": SIGNATURE, "typ": "JWT", "kid": jwk.JWK(**signing_key).thumbprint()})

    envelope = jwe.JWE(signed.serialize(compact=True).encode(),
                       protected={"alg": KEY_ENCRYPTION, "enc": CONTENT_ENCRYPTION, "cty": "JWT",
                                  "kid": gateway_key["kid"]})
    envelope.add_recipient(jwk.JWK(**gateway_key))
    return envelope.serialize(compact=True)
