"""Stateless, fixed-route public relay. Only the internal API may persist data."""

import logging
import ssl
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.connect.protocol import (
    PRIVATE_HEADERS,
    bounded_json,
    json_object,
    verify_signature,
)
from app.registration.schema import parse_submission, submission_shape

ASSETS = Path(__file__).resolve().parents[1] / "registration/templates"


def create_app(settings, *, transport=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    host = urlsplit(settings.public_origin).netloc
    tls = ssl.create_default_context(cafile=settings.ca_file)
    # This dedicated process must not emit bearer headers/request transport traces.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    for name in list(logging.Logger.manager.loggerDict):
        if name.startswith("httpcore."):
            logging.getLogger(name).setLevel(logging.WARNING)

    @app.middleware("http")
    async def protect(request, call_next):
        if request.headers.get("host") != host:
            return HTMLResponse(
                "Use the configured Connect address.", 403, headers=PRIVATE_HEADERS
            )
        response = await call_next(request)
        response.headers.update(PRIVATE_HEADERS)
        return response

    async def forward(path, raw, signature=None):
        headers = {
            "Authorization": "Bearer " + settings.api_secret.get_secret_value(),
            "Content-Type": "application/json",
        }
        if signature:
            headers["Tally-Signature"] = signature
        try:
            async with (
                httpx.AsyncClient(
                    timeout=httpx.Timeout(12, connect=4),
                    trust_env=False,
                    follow_redirects=False,
                    verify=tls,
                    transport=transport,
                ) as client,
                client.stream(
                    "POST",
                    settings.internal_origin + path,
                    content=raw,
                    headers=headers,
                ) as response,
            ):
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > 4096:
                        raise ValueError("Internal reply exceeds limit.")
                    body.extend(chunk)
                if response.status_code == 200:
                    expected = (
                        {"received": True}
                        if path.endswith("/submissions")
                        else {"confirmed": True}
                    )
                    if json_object(body) != expected:
                        raise ValueError("Unexpected internal reply.")
                    return expected
                if response.status_code in (400, 409) and path.endswith("/confirm"):
                    raise HTTPException(
                        400,
                        "This confirmation link is invalid, expired or already used.",
                    )
                if response.status_code == 422 and path.endswith("/submissions"):
                    raise HTTPException(422, "Invalid registration submission.")
        except (httpx.HTTPError, ValueError, TypeError):
            pass
        # No acknowledgement while the durable internal commit is unavailable/uncertain.
        raise HTTPException(
            503,
            "Registration processing is temporarily unavailable. Please try again.",
            headers={"Retry-After": "30"},
        )

    @app.post("/webhooks/tally/registrations")
    async def receive(request: Request):
        raw = await bounded_json(request, 128 * 1024)
        signature = request.headers.get("tally-signature", "")
        if not verify_signature(
            raw, signature, settings.tally_signing_secret.get_secret_value()
        ):
            raise HTTPException(401, "Invalid webhook signature.")
        payload = None
        try:
            payload = json_object(raw)
            parse_submission(payload)
        except (ValueError, TypeError, KeyError, UnicodeError, AttributeError):
            logging.getLogger("uvicorn.error").warning(
                "Registration webhook format rejected; shape=%s",
                submission_shape(payload),
            )
            raise HTTPException(422, "Invalid registration submission.") from None
        return await forward("/v1/registrations/submissions", raw, signature)

    @app.get("/")
    def home():
        return HTMLResponse((ASSETS / "home.html").read_text())

    @app.get("/confirm")
    def page():
        return HTMLResponse((ASSETS / "confirm.html").read_text())

    @app.get("/assets/confirmation.js")
    def script():
        return FileResponse(ASSETS / "confirmation.js", media_type="text/javascript")

    @app.get("/assets/confirmation.css")
    def style():
        return FileResponse(ASSETS / "confirmation.css", media_type="text/css")

    @app.post("/confirm")
    async def confirm(request: Request):
        if request.headers.get("origin") != settings.public_origin:
            raise HTTPException(403, "Use the confirmation page.")
        raw = await bounded_json(request, 2048)
        try:
            body = json_object(raw)
            token = body["token"]
            if set(body) != {"token"} or not isinstance(token, str) or len(token) != 43:
                raise ValueError()
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise HTTPException(
                400, "This confirmation link is invalid, expired or already used."
            ) from None
        return await forward("/v1/registrations/confirm", raw)

    return app


def from_environment():
    from app.connect.settings import ConnectSettings

    return create_app(ConnectSettings())
