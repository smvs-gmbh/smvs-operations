"""Small shared HTTP boundary; no application or database dependencies."""

import base64
import hashlib
import hmac
import json
from urllib.parse import urlsplit

from fastapi import HTTPException


def canonical_origin(value, development=False):
    parsed = urlsplit(value)
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
        or not (
            parsed.scheme == "https"
            or (
                development
                and parsed.scheme == "http"
                and parsed.hostname == "localhost"
            )
        )
    ):
        raise ValueError("Use a canonical HTTPS origin, or localhost for development.")
    # Also reject malformed ports at startup.
    _ = parsed.port
    return parsed


def verify_signature(raw, supplied, secret):
    expected = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest())
    return hmac.compare_digest(expected, supplied.encode())


async def bounded_json(request, limit):
    if (
        request.headers.get("content-type", "").split(";")[0].strip()
        != "application/json"
    ):
        raise HTTPException(415, "Use JSON.")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > limit:
            raise HTTPException(413, "Request is too large.")
        raw.extend(chunk)
    return bytes(raw)


def json_object(raw):
    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("Duplicate JSON key.")
            data[key] = value
        return data

    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise TypeError("Use a JSON object.")
    return value


PRIVATE_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}
