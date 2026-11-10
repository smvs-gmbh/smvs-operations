"""Internal-only registration review; public intake routes are a separate ASGI app."""

from collections import Counter

import httpx
from cryptography.fernet import InvalidToken
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.db.session import get_session_factory
from app.domain.crm import registrations as service
from app.domain.crm.registration_sync import configuration, pull, resend_confirmation
from app.domain.models import (
    CRMContact,
    CRMEndUser,
    EndUserRegistration,
    RegistrationEvent,
)
from app.portal.exception_routes import review_form
from app.portal.queries import paged
from app.portal.record_navigation import filter_query, list_record_navigation
from app.portal.routes import DbSession, templates
from app.portal.table_views import prepare

router = APIRouter()
PATH = "/workflows/registrations"
PRIVATE = {"Cache-Control": "no-store", "Referrer-Policy": "same-origin"}


def actor(request):
    user = getattr(request.state, "portal_user", None)
    if not user or not getattr(user, "is_nmvo", False):
        raise HTTPException(
            403, "Sign in with an NMVO account to review registrations."
        )
    return user.id, user.email


def get(session, identifier):
    row = session.get(EndUserRegistration, identifier)
    if not row:
        raise HTTPException(404, "Registration not found.")
    return row


def direct_delivery():
    return getattr(get_settings(), "registration_delivery_mode", "buffered") == "direct"


def configured():
    if direct_delivery():
        return bool(
            get_settings().registration_encryption_key
            and get_settings().connect_api_secret
        )
    try:
        configuration(get_settings())
        return True
    except ValueError:
        return False


def directory_statement(q="", status=""):
    statement = (
        select(EndUserRegistration, CRMEndUser, CRMContact)
        .outerjoin(CRMEndUser, CRMEndUser.id == EndUserRegistration.end_user_id)
        .outerjoin(CRMContact, CRMContact.id == EndUserRegistration.contact_id)
    )
    if status:
        statement = statement.where(EndUserRegistration.status == status)
    if q:
        statement = statement.where(
            or_(
                CRMEndUser.name.contains(q, autoescape=True),
                CRMContact.profile["email"].as_string().contains(q, autoescape=True),
            )
        )
    return statement


@router.get(PATH, include_in_schema=False)
def directory(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    status: str = Query("", max_length=30),
    page: int = Query(1, ge=1),
):
    prepare(request, session, "registrations")
    if status and status not in service.STATUSES:
        raise HTTPException(422, "Choose a valid registration status.")
    statement = directory_statement(q, status)
    rows, pagination = paged(
        session,
        statement.order_by(
            EndUserRegistration.received_at.desc(), EndUserRegistration.id.desc()
        ),
        page,
        view_request=request,
        table_key="registrations",
    )
    counts = Counter(session.scalars(select(EndUserRegistration.status)))
    return templates.TemplateResponse(
        request=request,
        name="registration_workflow.html",
        headers=PRIVATE,
        context={
            "title": "End-user registrations",
            "active": "workflows",
            "rows": rows,
            "pagination": pagination,
            "q": q,
            "status": status,
            "statuses": service.STATUSES,
            "counts": counts,
            "configured": configured(),
            "direct_delivery": direct_delivery(),
        },
    )


@router.post(PATH + "/sync", include_in_schema=False)
async def synchronise(request: Request):
    actor(request)
    await review_form(request)
    if direct_delivery():
        raise HTTPException(
            409, "Connect registrations are stored directly; no pull is required."
        )
    try:
        await run_in_threadpool(pull, get_session_factory(), get_settings())
    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
        KeyError,
        InvalidToken,
        SQLAlchemyError,
    ):
        raise HTTPException(
            502,
            "Registration synchronisation failed. Check the intake configuration and try again.",
        ) from None
    return RedirectResponse(PATH, status_code=303)


@router.get(PATH + "/{identifier}", include_in_schema=False)
def detail(request: Request, identifier: int, session: DbSession):
    row = get(session, identifier)
    user = session.get(CRMEndUser, row.end_user_id) if row.end_user_id else None
    contact = session.get(CRMContact, row.contact_id) if row.contact_id else None
    return templates.TemplateResponse(
        request=request,
        name="registration_detail.html",
        headers=PRIVATE,
        context={
            "title": "Review registration",
            "active": "workflows",
            "registration": row,
            "end_user": user,
            "contact": contact,
            "profile": user.profile or {} if user else {},
            "contact_profile": contact.profile or {} if contact else {},
            "statuses": service.STATUSES,
            "duplicates": service.duplicate_candidates(session, row),
            "direct_delivery": direct_delivery(),
            "security_available": bool(
                row.security_ciphertext
                and row.security_expires_at > service.utcnow()
                and row.status == "ready_nmvs"
            ),
            "events": session.scalars(
                select(RegistrationEvent)
                .where(RegistrationEvent.registration_id == row.id)
                .order_by(RegistrationEvent.id)
            ).all(),
            "record_nav": list_record_navigation(
                session,
                directory_statement(
                    request.query_params.get("q", ""),
                    request.query_params.get("status", ""),
                ),
                EndUserRegistration.id,
                row.id,
                (EndUserRegistration.received_at.desc(), EndUserRegistration.id.desc()),
                PATH,
                "Registrations",
                view_request=request,
                table_key="registrations",
                back_query=filter_query(request),
                query=filter_query(request),
            ),
        },
    )


@router.post(PATH + "/{identifier}", include_in_schema=False)
async def update(request: Request, identifier: int, session: DbSession):
    operator = actor(request)
    data = await review_form(request)
    row = session.get(EndUserRegistration, identifier, with_for_update=True)
    if not row:
        raise HTTPException(404, "Registration not found.")
    if data.get("version") != str(row.version):
        raise HTTPException(409, "This registration changed. Reload before continuing.")
    if data.get("command") == "resend":
        if row.status != "awaiting_email":
            raise HTTPException(409, "Email confirmation is no longer pending.")
        if direct_delivery():
            from app.registration.internal_service import resend

            key = get_settings().registration_encryption_key
            if not key:
                raise HTTPException(503, "Configure the registration encryption key.")
            try:
                resend(session, row, operator, key.get_secret_value())
                session.commit()
            except ValueError as e:
                session.rollback()
                raise HTTPException(409, str(e)) from None
            except StaleDataError:
                session.rollback()
                raise HTTPException(
                    409, "This registration changed. Reload before continuing."
                ) from None
            return RedirectResponse(
                PATH + "/" + str(identifier) + filter_query(request, "q", "status"),
                status_code=303,
            )
        intake_id, revision = row.intake_id, row.intake_revision
        service.event(session, row, operator, "confirmation_resend_requested")
        session.commit()
        try:
            await run_in_threadpool(
                resend_confirmation, get_settings(), intake_id, revision
            )
        except (httpx.HTTPError, ValueError):
            raise HTTPException(
                409,
                "Synchronise the registration and check its confirmation status before resending.",
            ) from None
        return RedirectResponse(
            PATH + "/" + str(identifier) + filter_query(request, "q", "status"),
            status_code=303,
        )
    try:
        service.act(
            session,
            row,
            data.get("command"),
            operator,
            data.get("note", ""),
            data.get("nmvs_id", ""),
            data.get("duplicates_checked") == "yes",
        )
        session.commit()
    except ValueError as e:
        session.rollback()
        raise HTTPException(409, str(e)) from None
    except StaleDataError:
        session.rollback()
        raise HTTPException(
            409, "This registration changed. Reload before continuing."
        ) from None
    return RedirectResponse(
        PATH + "/" + str(identifier) + filter_query(request, "q", "status"),
        status_code=303,
    )


@router.post(PATH + "/{identifier}/security", include_in_schema=False)
async def reveal(request: Request, identifier: int, session: DbSession):
    operator = actor(request)
    data = await review_form(request)
    row = session.get(EndUserRegistration, identifier, with_for_update=True)
    if not row:
        raise HTTPException(404, "Registration not found.")
    if data.get("version") != str(row.version):
        raise HTTPException(
            409, "Reload the registration before viewing security data."
        )
    key = get_settings().registration_encryption_key
    if not key:
        raise HTTPException(503, "Configure the registration encryption key.")
    try:
        values = service.security_data(session, row, key.get_secret_value(), operator)
        session.commit()
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    return templates.TemplateResponse(
        request=request,
        name="registration_security.html",
        headers=PRIVATE,
        context={
            "title": "Temporary NMVS security data",
            "active": "workflows",
            "registration": row,
            "security": values,
        },
    )


@router.post(PATH + "/{identifier}/delete", include_in_schema=False)
async def delete_registration(request: Request, identifier: int, session: DbSession):
    from app.domain.crm.deletion import erase_registration

    admin = deletion_admin(request)
    data = await review_form(request)
    row = session.get(EndUserRegistration, identifier, with_for_update=True)
    if not row:
        raise HTTPException(404, "Registration not found.")
    validate_deletion(data, row)
    if not direct_delivery():
        raise HTTPException(
            409, "Delete the legacy intake copy before deleting this registration."
        )
    try:
        erase_registration(session, row, admin, data.get("include_crm") == "yes")
        session.commit()
    except ValueError as error:
        session.rollback()
        from app.portal.deletion_review import render_deletion_review

        return render_deletion_review(request, session, row, None, str(error), 409)
    return RedirectResponse(PATH, status_code=303)


def deletion_admin(request):
    user = getattr(request.state, "portal_user", None)
    if not user or not getattr(user, "is_admin", False):
        raise HTTPException(403, "Only administrators can permanently delete records.")
    return user


def validate_deletion(data, row):
    if data.get("version") != str(row.version):
        raise HTTPException(409, "This record changed. Reload before deleting.")
    if data.get("confirm_delete") != "yes":
        raise HTTPException(422, "Confirm permanent deletion explicitly.")
