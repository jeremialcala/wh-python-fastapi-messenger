# -*- coding: utf-8 -*-
from jwcrypto import jwk

ALGORITHM = "ES256"


def public_signing_key(candidate) -> dict:
    """
        Turns what a client sends as its signing key into what the registry stores: a public P-256 key and nothing
        else, with its thumbprint as kid. Anything that is not exactly that raises ValueError, and so does a
        private key: the gateway must never hold one of a client's.
    """
    if not isinstance(candidate, dict):
        raise ValueError("The signing key must be a JWK")
    if "d" in candidate:
        raise ValueError("That is a private key: only the public part is registered")
    if candidate.get("kty") != "EC" or candidate.get("crv") != "P-256":
        raise ValueError("The signing key must be an EC key on the P-256 curve")
    x, y = candidate.get("x"), candidate.get("y")
    if not isinstance(x, str) or not isinstance(y, str):
        raise ValueError("The signing key has no coordinates")
    try:
        key = jwk.JWK(kty="EC", crv="P-256", x=x, y=y)
        # Building the verification key checks that the point is on the curve.
        key.get_op_key("verify")
    except Exception:
        raise ValueError("The signing key is not a valid point of the P-256 curve") from None
    return {"kty": "EC", "crv": "P-256", "x": x, "y": y, "kid": key.thumbprint(), "use": "sig", "alg": ALGORITHM}
