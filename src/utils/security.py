# -*- coding: utf-8 -*-
import hashlib
import hmac
import re

SIGNATURE_PREFIX = "sha256="


def secrets_match(expected: str | None, received: str | None) -> bool:
    """Constant-time comparison that never matches when either side is missing."""
    if not expected or not received:
        return False
    return hmac.compare_digest(expected.encode(), received.encode())


def looks_like_signature(header: str | None) -> bool:
    """
        Whether the header has the shape of one Meta sends: "sha256=" and 64 hexadecimal digits. Telling it says
        nothing about any secret, so it is checked before one is opened.
    """
    return bool(header) and re.fullmatch("sha256=[0-9a-f]{64}", header) is not None


def is_valid_signature(secret: str | None, body: bytes, header: str | None) -> bool:
    """
    Checks Meta's X-Hub-Signature-256 header: "sha256=" + HMAC-SHA256 of the raw body, keyed with the App Secret.

    :param secret: the Meta App Secret; without one nothing can be verified, so nothing is accepted.
    :param body: the request body exactly as received, before any JSON parsing.
    :param header: the value of the X-Hub-Signature-256 header.
    """
    if not secret or not header or not header.startswith(SIGNATURE_PREFIX):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return secrets_match(expected, header[len(SIGNATURE_PREFIX):])
