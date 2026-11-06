"""Passkey enrolment, sign-in and internal user administration."""

import json
from datetime import timedelta
from secrets import token_bytes

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.config import get_settings
from app.domain.auth import service as auth
from app.domain.models import PortalAuthToken, PortalPasskey, PortalUser
from app.integration.artifacts.storage import utcnow
from app.portal.exception_routes import review_form
from app.portal.routes import DbSession, templates

router = APIRouter()
UV = UserVerificationRequirement.REQUIRED
PRIVATE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
# The browser needs to send a same-origin Origin header for HTML form POSTs.
ADMIN_PAGE_HEADERS = {**PRIVATE, "Referrer-Policy": "same-origin"}


def settings_for_auth():
    settings = get_settings()
    if not settings.portal_auth_enabled:
        raise HTTPException(404, "Portal authentication is disabled.")
    return settings


async def payload(request, settings):
    if request.headers.get("origin") != settings.portal_auth_origin:
        raise HTTPException(403, "Use the configured portal origin.")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Use the portal sign-in page.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise HTTPException(413, "Passkey response is too large.")
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(422, "Invalid passkey request.") from None
    if not isinstance(value, dict):
        raise HTTPException(422, "Invalid passkey request.")
    return value


def set_cookie(response, name, value, lifetime, secure):
    response.set_cookie(
        name,
        value,
        max_age=int(lifetime.total_seconds()),
        secure=secure,
        httponly=True,
        samesite="strict",
        path="/",
    )


@router.get("/auth/login", include_in_schema=False)
def login(request: Request):
    settings_for_auth()
    return templates.TemplateResponse(
        request=request,
        name="portal_login.html",
        context={},
        headers=PRIVATE,
    )


@router.post("/auth/{mode}/options", include_in_schema=False)
async def ceremony_options(request: Request, mode: str, session: DbSession):
    settings = settings_for_auth()
    rp_id, secure = auth.origin_config(settings)
    data = await payload(request, settings)
    challenge = token_bytes(32)
    if mode == "enrol":
        invite = auth.get_token(session, data.get("invitation"), "invite")
        user = session.get(PortalUser, invite.user_id) if invite else None
        if not user or user.disabled_at:
            raise HTTPException(403, "This invitation is invalid or has expired.")
        keys = session.scalars(
            select(PortalPasskey).where(PortalPasskey.user_id == user.id)
        )
        options = generate_registration_options(
            rp_id=rp_id,
            rp_name=settings.app_name,
            user_name=user.email,
            user_id=bytes.fromhex(user.handle),
            challenge=challenge,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UV,
            ),
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=base64url_to_bytes(key.credential_id))
                for key in keys
            ],
        )
    elif mode == "signin":
        invite = user = None
        options = generate_authentication_options(
            rp_id=rp_id, challenge=challenge, user_verification=UV
        )
    else:
        raise HTTPException(404, "Unknown passkey operation.")
    auth.prune_tokens(session)
    raw = auth.issue_token(
        session,
        mode,
        auth.CHALLENGE_LIFETIME,
        user_id=user.id if user else None,
        challenge=bytes_to_base64url(challenge),
        invitation_id=invite.id if invite else None,
    )
    session.commit()
    response = JSONResponse(json.loads(options_to_json(options)), headers=PRIVATE)
    set_cookie(response, auth.CHALLENGE_COOKIE, raw, auth.CHALLENGE_LIFETIME, secure)
    return response


@router.post("/auth/{mode}/finish", include_in_schema=False)
async def ceremony_finish(request: Request, mode: str, session: DbSession):
    settings = settings_for_auth()
    rp_id, secure = auth.origin_config(settings)
    data = await payload(request, settings)
    if mode not in {"enrol", "signin"}:
        raise HTTPException(404, "Unknown passkey operation.")
    token = auth.get_token(
        session, request.cookies.get(auth.CHALLENGE_COOKIE), mode, lock=True
    )
    credential = data.get("credential")
    if not token or not isinstance(credential, dict):
        raise HTTPException(403, "Start a new passkey request.")
    verification = {
        "credential": credential,
        "expected_challenge": base64url_to_bytes(token.challenge),
        "expected_rp_id": rp_id,
        "expected_origin": settings.portal_auth_origin,
        "require_user_verification": True,
    }
    invite = None
    try:
        if mode == "enrol":
            invite = auth.get_token(
                session, data.get("invitation"), "invite", lock=True
            )
            user = session.get(PortalUser, token.user_id, with_for_update=True)
            if (
                not invite
                or invite.id != token.invitation_id
                or not user
                or user.disabled_at
            ):
                raise ValueError()
            result = verify_registration_response(**verification)
            session.add(
                PortalPasskey(
                    id=auth.digest(result.credential_id),
                    user_id=user.id,
                    credential_id=bytes_to_base64url(result.credential_id),
                    public_key=bytes_to_base64url(result.credential_public_key),
                    sign_count=result.sign_count,
                )
            )
        else:
            credential_id = base64url_to_bytes(credential.get("id", ""))
            key = session.get(
                PortalPasskey, auth.digest(credential_id), with_for_update=True
            )
            user = (
                session.get(PortalUser, key.user_id, with_for_update=True)
                if key
                else None
            )
            if not user or user.disabled_at:
                raise ValueError()
            user_handle = credential.get("response", {}).get("userHandle")
            if user_handle is not None and base64url_to_bytes(
                user_handle
            ) != bytes.fromhex(user.handle):
                raise ValueError()
            result = verify_authentication_response(
                **verification,
                credential_public_key=base64url_to_bytes(key.public_key),
                credential_current_sign_count=key.sign_count,
            )
            key.sign_count = result.new_sign_count
    except (WebAuthnException, ValueError, TypeError, AttributeError):
        session.delete(token)
        session.commit()
        raise HTTPException(403, "Passkey verification failed. Try again.") from None
    session.delete(token)
    if invite:
        session.delete(invite)
    raw = auth.issue_token(session, "session", auth.SESSION_LIFETIME, user_id=user.id)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "This passkey could not be registered.") from None
    response = JSONResponse(
        {"next": "/products" if user.is_nmvo else "/admin/users"}, headers=PRIVATE
    )
    response.delete_cookie(auth.CHALLENGE_COOKIE)
    set_cookie(response, auth.SESSION_COOKIE, raw, auth.SESSION_LIFETIME, secure)
    return response


@router.post("/auth/logout", include_in_schema=False)
async def logout(request: Request, session: DbSession):
    settings = settings_for_auth()
    await review_form(request, expected_origin=settings.portal_auth_origin)
    token = auth.get_token(
        session, request.cookies.get(auth.SESSION_COOKIE), "session", lock=True
    )
    if token:
        session.delete(token)
        session.commit()
    response = RedirectResponse("/auth/login", status_code=303, headers=PRIVATE)
    response.delete_cookie(auth.SESSION_COOKIE)
    return response


@router.post("/auth/backup-passkey", include_in_schema=False)
async def backup_passkey(request: Request, session: DbSession):
    settings = settings_for_auth()
    await review_form(request, expected_origin=settings.portal_auth_origin)
    token = auth.get_token(
        session, request.cookies.get(auth.SESSION_COOKIE), "session", lock=True
    )
    if not token or utcnow() - token.created_at > timedelta(minutes=5):
        raise HTTPException(403, "Sign out and sign in again before adding a passkey.")
    user = session.get(PortalUser, token.user_id, with_for_update=True)
    if not user or user.disabled_at:
        raise HTTPException(403, "This account is unavailable.")
    raw = auth.issue_token(session, "invite", timedelta(minutes=5), user_id=user.id)
    session.commit()
    next_url = f"/auth/login#{raw}"
    if request.headers.get("accept") == "application/json":
        return JSONResponse({"next": next_url}, headers=PRIVATE)
    return RedirectResponse(next_url, status_code=303, headers=PRIVATE)


def user_admin(request, session, invitation=None):
    users = session.scalars(select(PortalUser).order_by(PortalUser.email)).all()
    return templates.TemplateResponse(
        request=request,
        name="portal_users.html",
        context={
            "title": "Users",
            "active": "users",
            "users": users,
            "invitation": invitation,
            "enrolled": set(session.scalars(select(PortalPasskey.user_id))),
        },
        headers=ADMIN_PAGE_HEADERS,
    )


@router.get("/admin/users", include_in_schema=False)
def admin_users(request: Request, session: DbSession):
    return user_admin(request, session)


@router.post("/admin/users", include_in_schema=False)
async def create_user(request: Request, session: DbSession):
    settings = settings_for_auth()
    data = await review_form(request, expected_origin=settings.portal_auth_origin)
    try:
        raw = auth.invite_user(
            session,
            data.get("email", ""),
            admin=data.get("admin") == "yes",
            nmvo=data.get("nmvo") == "yes",
        )
        session.commit()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "An account already uses this email.") from None
    return user_admin(
        request, session, auth.invitation_url(settings.portal_auth_origin, raw)
    )


@router.post("/admin/users/{identifier}", include_in_schema=False)
async def change_user(request: Request, identifier: int, session: DbSession):
    settings = settings_for_auth()
    data = await review_form(request, expected_origin=settings.portal_auth_origin)
    if identifier == request.state.portal_user.id:
        raise HTTPException(409, "Another administrator must manage your account.")
    admins = list(
        session.scalars(
            select(PortalUser)
            .where(PortalUser.is_admin == 1, PortalUser.disabled_at.is_(None))
            .order_by(PortalUser.id)
            .with_for_update()
        )
    )
    if not any(admin.id == request.state.portal_user.id for admin in admins):
        raise HTTPException(403, "Administrator access is required.")
    user = session.get(PortalUser, identifier, with_for_update=True)
    if not user:
        raise HTTPException(404, "User not found.")
    command = data.get("command")
    if command == "disable":
        user.disabled_at = utcnow()
    elif command == "enable":
        user.disabled_at = None
    elif command == "roles":
        admin, nmvo = data.get("admin") == "yes", data.get("nmvo") == "yes"
        if not (admin or nmvo):
            raise HTTPException(422, "Select at least one role.")
        user.is_admin, user.is_nmvo = int(admin), int(nmvo)
    elif command == "reinvite":
        if user.disabled_at or session.scalar(
            select(PortalPasskey.id).where(PortalPasskey.user_id == user.id).limit(1)
        ):
            raise HTTPException(
                409, "Only active accounts without a passkey can be reinvited."
            )
        session.execute(
            delete(PortalAuthToken).where(PortalAuthToken.user_id == user.id)
        )
        raw = auth.issue_token(
            session, "invite", auth.INVITATION_LIFETIME, user_id=user.id
        )
        session.commit()
        return user_admin(
            request, session, auth.invitation_url(settings.portal_auth_origin, raw)
        )
    else:
        raise HTTPException(422, "Select a valid user action.")
    session.execute(delete(PortalAuthToken).where(PortalAuthToken.user_id == user.id))
    session.commit()
    return RedirectResponse("/admin/users", status_code=303)
