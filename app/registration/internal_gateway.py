"""Dedicated private API: only two authenticated registration commands, no portal."""

import hmac
from ipaddress import ip_address

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from app.connect.protocol import (
    PRIVATE_HEADERS,
    bounded_json,
    json_object,
    verify_signature,
)
from app.domain.models import RegistrationReceipt
from app.registration import internal_service
from app.registration.schema import parse_submission


def create_app(settings, factory):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    allowed = {
        ip_address(value.strip())
        for value in settings.registration_api_allowed_ips.split(",")
        if value.strip()
    }

    @app.middleware("http")
    async def protect(request, call_next):
        try:
            permitted = request.client and ip_address(request.client.host) in allowed
        except ValueError:
            permitted = False
        if not permitted:
            return JSONResponse(
                {"detail": "This source cannot access the registration API."},
                403,
                headers=PRIVATE_HEADERS,
            )
        expected = "Bearer " + settings.connect_api_secret.get_secret_value()
        if not hmac.compare_digest(
            request.headers.get("authorization", "").encode(), expected.encode()
        ):
            return JSONResponse(
                {"detail": "Registration API authentication required."},
                401,
                headers=PRIVATE_HEADERS,
            )
        response = await call_next(request)
        response.headers.update(PRIVATE_HEADERS)
        return response

    @app.post("/v1/registrations/submissions")
    async def submissions(request: Request):
        raw = await bounded_json(request, 128 * 1024)
        if not verify_signature(
            raw,
            request.headers.get("tally-signature", ""),
            settings.tally_registration_signing_secret.get_secret_value(),
        ):
            raise HTTPException(401, "Invalid webhook signature.")
        try:
            payload = json_object(raw)
            event, submission, _, _ = parse_submission(payload)
        except (ValueError, TypeError, KeyError, UnicodeError, AttributeError):
            raise HTTPException(422, "Invalid registration submission.") from None
        try:
            with factory.begin() as session:
                internal_service.receive(session, payload, settings)
        except IntegrityError:
            # Only acknowledge a concurrent retry AFTER its complete CRM transaction committed.
            from app.domain.models import EndUserRegistration

            with factory() as session:
                receipt = session.scalar(
                    select(RegistrationReceipt).where(
                        or_(
                            RegistrationReceipt.event_id == event,
                            RegistrationReceipt.submission_id == submission,
                        )
                    )
                )
                if receipt is None or not session.scalar(
                    select(EndUserRegistration.id).where(
                        EndUserRegistration.intake_id == receipt.id
                    )
                ):
                    raise HTTPException(
                        503, "Registration processing is temporarily unavailable."
                    ) from None
        except (SQLAlchemyError, ValueError):
            raise HTTPException(
                503, "Registration processing is temporarily unavailable."
            ) from None
        return {"received": True}

    @app.post("/v1/registrations/confirm")
    async def confirmation(request: Request):
        try:
            body = json_object(await bounded_json(request, 2048))
            if set(body) != {"token"}:
                raise ValueError()
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise HTTPException(400, "Invalid confirmation.") from None
        try:
            with factory.begin() as session:
                accepted = internal_service.confirm(
                    session, body.get("token"), settings
                )
        except StaleDataError:
            accepted = False
        except SQLAlchemyError:
            raise HTTPException(
                503, "Registration processing is temporarily unavailable."
            ) from None
        if not accepted:
            raise HTTPException(400, "Invalid confirmation.")
        return {"confirmed": True}

    return app


def from_environment():
    from app.core.db.session import get_session_factory
    from app.registration.internal_settings import InternalRegistrationSettings

    return create_app(InternalRegistrationSettings(), get_session_factory())
