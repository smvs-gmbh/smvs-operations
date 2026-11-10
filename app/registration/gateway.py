"""Separate public ASGI app: no Operations routers, sessions, DB or NMVS secrets."""

import base64
import hashlib
import hmac
import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.registration import service
from app.registration.crypto import cipher

MAX_BODY = 128 * 1024


async def bounded_json(request, limit=MAX_BODY):
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Use JSON.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise HTTPException(413, "Request is too large.")
        body.extend(chunk)
    return bytes(body)


def json_object(raw):
    def unique(pairs):
        data = {}
        for k, v in pairs:
            if k in data:
                raise ValueError()
            data[k] = v
        return data

    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise TypeError()
    return value


def create_app(settings, factory):
    origin = urlsplit(settings.registration_public_origin)
    if origin.scheme != "https" and not (
        settings.registration_environment == "development"
        and origin.hostname == "localhost"
    ):
        raise ValueError("The public registration origin requires HTTPS.")
    if (
        origin.path
        or origin.query
        or origin.fragment
        or origin.username
        or origin.password
        or not origin.hostname
    ):
        raise ValueError("Configure a canonical registration origin.")
    cipher(settings.registration_encryption_key.get_secret_value())
    if (
        min(
            len(settings.registration_exchange_secret.get_secret_value()),
            len(settings.tally_registration_signing_secret.get_secret_value()),
        )
        < 32
    ):
        raise ValueError(
            "Use independent registration exchange and signing secrets of at least 32 characters."
        )
    if (
        len(
            {
                settings.registration_encryption_key.get_secret_value(),
                settings.registration_exchange_secret.get_secret_value(),
                settings.tally_registration_signing_secret.get_secret_value(),
            }
        )
        != 3
    ):
        raise ValueError("Use independent encryption, exchange and webhook secrets.")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def protection(request, call_next):
        if request.headers.get("host") != origin.netloc:
            return HTMLResponse(
                "Use the configured registration address.", status_code=403
            )
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            }
        )
        return response

    @app.post("/webhooks/tally/registrations")
    async def webhook(request: Request):
        raw = await bounded_json(request)
        signature = base64.b64encode(
            hmac.new(
                settings.tally_registration_signing_secret.get_secret_value().encode(),
                raw,
                hashlib.sha256,
            ).digest()
        ).decode()
        if not hmac.compare_digest(
            signature.encode(), request.headers.get("tally-signature", "").encode()
        ):
            raise HTTPException(401, "Invalid webhook signature.")
        try:
            payload = json_object(raw)
            with factory.begin() as session:
                service.receive(
                    session,
                    payload,
                    settings.registration_encryption_key.get_secret_value(),
                    settings.registration_security_ttl_days,
                )
        except IntegrityError:
            # A concurrent retry is acknowledged only when its durable source ID exists.
            from sqlalchemy import or_, select

            from app.registration.models import IntakeRegistration

            event, submission = (
                payload.get("eventId"),
                payload.get("data", {}).get("submissionId"),
            )
            with factory() as session:
                if not session.scalar(
                    select(IntakeRegistration.id).where(
                        or_(
                            IntakeRegistration.event_id == event,
                            IntakeRegistration.submission_id == submission,
                        )
                    )
                ):
                    raise
        except (ValueError, TypeError, KeyError, UnicodeError, AttributeError):
            raise HTTPException(422, "Invalid registration submission.") from None
        return {"received": True}

    @app.get("/confirm", response_class=HTMLResponse)
    def confirmation():
        return HTMLResponse(
            (Path(__file__).parent / "templates/confirm.html").read_text()
        )

    @app.get("/assets/confirmation.js")
    def confirmation_script():
        return FileResponse(
            Path(__file__).parent / "templates/confirmation.js",
            media_type="text/javascript",
        )

    @app.get("/assets/confirmation.css")
    def confirmation_style():
        return FileResponse(
            Path(__file__).parent / "templates/confirmation.css", media_type="text/css"
        )

    @app.post("/confirm")
    async def verify_email(request: Request):
        if request.headers.get("origin") != settings.registration_public_origin:
            raise HTTPException(403, "Use the confirmation page.")
        try:
            body = json_object(await bounded_json(request, 2048))
            with factory.begin() as session:
                success = service.confirm(session, body.get("token"))
        except (ValueError, TypeError, KeyError, UnicodeError, StaleDataError):
            success = False
        if not success:
            raise HTTPException(
                400, "This confirmation link is invalid, expired or already used."
            )
        return {"confirmed": True}

    def exchange_access(request):
        expected = "Bearer " + settings.registration_exchange_secret.get_secret_value()
        if not hmac.compare_digest(
            request.headers.get("authorization", "").encode(), expected.encode()
        ):
            raise HTTPException(401, "Exchange authentication required.")

    @app.get("/exchange/registrations")
    def exchange(request: Request):
        exchange_access(request)
        with factory.begin() as session:
            return {
                "registrations": service.exchange_rows(
                    session, settings.registration_encryption_key.get_secret_value()
                )
            }

    @app.post("/exchange/registrations/ack")
    async def acknowledge(request: Request):
        exchange_access(request)
        try:
            data = json_object(await bounded_json(request, 2048))
            with factory.begin() as session:
                service.acknowledge(session, data["id"], data["revision"])
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise HTTPException(422, "Invalid acknowledgement.") from None
        return {"acknowledged": True}

    @app.post("/exchange/registrations/resend")
    async def resend(request: Request):
        exchange_access(request)
        try:
            data = json_object(await bounded_json(request, 2048))
            with factory.begin() as session:
                service.resend(
                    session,
                    data["id"],
                    data["revision"],
                    settings.registration_encryption_key.get_secret_value(),
                )
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise HTTPException(
                409,
                "Confirmation cannot be resent yet. Synchronise and check its status.",
            ) from None
        return {"queued": True}

    return app


def from_environment():
    from app.registration.settings import IntakeSettings
    from app.registration.store import factory

    settings = IntakeSettings()
    return create_app(settings, factory(settings))
