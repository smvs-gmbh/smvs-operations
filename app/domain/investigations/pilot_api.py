"""Loopback-only Collaboration API for local development."""

import hmac
import os
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.alert_desk.schema import Capability, Findings
from app.connect.protocol import PRIVATE_HEADERS
from app.core.config import get_settings
from app.core.db.session import SessionFactory
from app.domain.investigations import access_api, pilot
from app.domain.models import AlertDeskEvent


def create_app(sessions, secret):
    if len(secret) < 32:
        raise ValueError(
            "Set a dedicated Alert Desk pilot secret of at least 32 characters."
        )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def protect(request, call_next):
        expected = ("Bearer " + secret).encode()
        supplied = request.headers.get("authorization", "").encode()
        if (
            not request.client
            or request.client.host != "127.0.0.1"
            or not hmac.compare_digest(expected, supplied)
        ):
            return JSONResponse(
                {"detail": "Access denied."}, 403, headers=PRIVATE_HEADERS
            )
        response = await call_next(request)
        response.headers.update(PRIVATE_HEADERS)
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        return JSONResponse({"detail": "Invalid request."}, 422)

    def session_token(request: Request):
        try:
            return Capability(token=request.headers.get("x-case-session", "")).token
        except ValueError:
            raise HTTPException(404, "Case unavailable.") from None

    def require_grant(session, token, **options):
        grant = pilot.active_grant(session, token, **options)
        if grant is None:
            raise HTTPException(404, "Case unavailable.")
        return grant

    @app.post("/exchange")
    def exchange(body: Capability):
        with sessions() as session, session.begin():
            grant = require_grant(session, body.token, invitation=True, lock=True)
            token = secrets.token_urlsafe(32)
            grant.invite_hash = None
            grant.session_hash = pilot.digest(token)
            pilot.append_event(session, grant, "Invitation accepted")
        return {"token": token}

    @app.get("/case")
    def read(token: Annotated[str, Depends(session_token)]):
        with sessions() as session:
            grant = require_grant(session, token)
            latest = session.scalar(
                select(AlertDeskEvent)
                .where(
                    AlertDeskEvent.grant_id == grant.id,
                    AlertDeskEvent.kind == "Findings submitted",
                )
                .order_by(AlertDeskEvent.id.desc())
                .limit(1)
            )
            return {
                "publication": grant.id,
                **{
                    key: value
                    for key, value in grant.publication.items()
                    if key != "recipient"
                },
                "latest": latest.data if latest else None,
            }

    @app.post("/findings")
    def submit(body: Findings, token: Annotated[str, Depends(session_token)]):
        with sessions() as session, session.begin():
            grant = require_grant(session, token, lock=True)
            if (
                grant.id != body.publication
                or body.basis is not None
                or body.batch_revision is not None
            ):
                raise HTTPException(409, "Reload the case before submitting.")
            if not body.matches_audience(grant.publication.get("audience", "end_user")):
                raise HTTPException(422, "Check your answers and try again.")
            key = str(body.submission_key)
            data = body.model_dump(
                mode="json",
                exclude={"submission_key", "publication", "basis", "batch_revision"},
            )
            previous = session.scalar(
                select(AlertDeskEvent).where(
                    AlertDeskEvent.grant_id == grant.id,
                    AlertDeskEvent.submission_key == key,
                )
            )
            if (
                previous
                and Findings(
                    submission_key=body.submission_key,
                    publication=body.publication,
                    **previous.data,
                )
                != body
            ):
                raise HTTPException(
                    409, "Reload the case before submitting a new finding."
                )
            if not previous:
                pilot.append_event(
                    session, grant, "Findings submitted", data=data, key=key
                )
        return {"received": True}

    access_api.install(app, sessions, secret)
    return app


def local_app():
    if get_settings().environment != "development":
        raise RuntimeError("The Alert Desk pilot is available only in development.")
    return create_app(SessionFactory, os.environ.get("ALERT_DESK_PILOT_SECRET", ""))
