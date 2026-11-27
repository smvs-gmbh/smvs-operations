"""Returning participants: mailbox proof, WebAuthn and revocable scoped sessions."""

import hmac
import json
import re
import secrets
from datetime import timedelta
from hashlib import sha256
from urllib.parse import urlsplit

from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy import delete, func, select
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

from app.alert_desk.schema import LoginCommand
from app.alert_desk.settings import mail_origin
from app.domain.investigations import access, audience, pilot, pilot_mail
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskAuthEvent,
    AlertDeskLoginThrottle,
    AlertDeskLoginToken,
    AlertDeskParticipantPasskey,
    AlertDeskParticipantSession,
    CRMContact,
)

NEUTRAL = "If access exists for this email address, you will receive a sign-in link."
UV = UserVerificationRequirement.REQUIRED


def keyed(secret, value):
    return hmac.digest(secret.encode(), value.encode(), "sha256").hex()


def binding(secret, grant):
    return keyed(
        secret,
        f"participant:{grant.id}:{grant.contact_id}:{grant.contact_version}:{grant.scope_key}:{grant.invited_at.isoformat()}",
    )


def eligible(session, identifier, secret, expected=None, *, lock=False):
    grant = session.get(
        AlertDeskAccess, identifier, with_for_update=lock, populate_existing=True
    )
    if not grant or grant.revoked_at or not grant.sent_at:
        return None
    linked = access.membership(session, grant)
    if not linked or (
        expected and not hmac.compare_digest(binding(secret, grant), expected)
    ):
        return None
    return grant, *linked


def resolve_session(session, raw, secret, *, lock=False):
    if not isinstance(raw, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", raw):
        return None
    row = session.get(
        AlertDeskParticipantSession,
        pilot.digest(raw),
        with_for_update=lock,
        populate_existing=True,
    )
    if row:
        if row.revoked_at or row.expires_at <= pilot.now():
            return None
        return eligible(session, row.access_id, secret, row.binding, lock=lock)
    old = access.lookup(session, AlertDeskAccess.session_hash, raw, lock=lock)
    return (
        old
        if old and old[0].session_expires_at and old[0].session_expires_at > pilot.now()
        else None
    )


def audit(session, kind, grant=None, **data):
    session.add(
        AlertDeskAuthEvent(
            access_id=grant.id if grant else None,
            occurred_at=pilot.now(),
            kind=kind,
            data=data,
        )
    )


def has_passkey(session, grant, secret):
    return session.scalar(select(AlertDeskParticipantPasskey.id).where(
        AlertDeskParticipantPasskey.access_id == grant.id,
        AlertDeskParticipantPasskey.binding == binding(secret, grant),
        AlertDeskParticipantPasskey.revoked_at.is_(None),
    ).limit(1)) is not None


def recently_verified(session, raw, grant):
    row = session.get(AlertDeskParticipantSession, pilot.digest(raw))
    since = row.created_at if row else grant.accepted_at
    return bool(since and since >= pilot.now() - timedelta(minutes=10))


def fresh(session, raw, grant):
    if not recently_verified(session, raw, grant):
        raise HTTPException(403, "Sign in again before managing passkeys.")


def issue_token(session, kind, data, minutes):
    raw = secrets.token_urlsafe(32)
    session.add(
        AlertDeskLoginToken(
            id=pilot.digest(raw),
            kind=kind,
            created_at=pilot.now(),
            expires_at=pilot.now() + timedelta(minutes=minutes),
            data=data,
        )
    )
    return raw


def take_token(session, raw, kind):
    if not raw:
        return None
    row = session.get(AlertDeskLoginToken, pilot.digest(raw), with_for_update=True)
    if not row or row.kind != kind:
        return None
    data = row.data if row.expires_at > pilot.now() else None
    session.delete(row)
    return data


def budget(session, secret, value, *, limit, minutes):
    now = pilot.now()
    identifier = keyed(secret, value)
    row = session.get(AlertDeskLoginThrottle, identifier, with_for_update=True)
    if not row:
        row = AlertDeskLoginThrottle(
            id=identifier, attempts=0, expires_at=now + timedelta(minutes=minutes)
        )
        session.add(row)
        session.flush()
    if row.expires_at <= now:
        row.attempts, row.expires_at = 0, now + timedelta(minutes=minutes)
    row.attempts += 1
    return row.attempts <= limit


def prune(session):
    session.execute(
        delete(AlertDeskLoginToken).where(AlertDeskLoginToken.expires_at <= pilot.now())
    )
    session.execute(
        delete(AlertDeskLoginThrottle).where(
            AlertDeskLoginThrottle.expires_at <= pilot.now()
        )
    )


def scopes_for_email(session, email, secret):
    result = []
    for identifier in session.scalars(
        select(AlertDeskAccess.id)
        .join(CRMContact, CRMContact.id == AlertDeskAccess.contact_id)
        .where(func.lower(CRMContact.profile["email"].as_string()) == email)
        .order_by(AlertDeskAccess.id)
    ):
        linked = eligible(session, identifier, secret)
        if linked and linked[2].strip().casefold() == email:
            result.append({"id": identifier, "binding": binding(secret, linked[0])})
    return result[:100]


def valid_scopes(session, scopes, secret):
    return [
        (item, linked)
        for item in scopes
        if (linked := eligible(session, item["id"], secret, item["binding"]))
    ]


def new_session(session, grant, secret, method):
    raw = secrets.token_urlsafe(32)
    session.add(
        AlertDeskParticipantSession(
            id=pilot.digest(raw),
            access_id=grant.id,
            binding=binding(secret, grant),
            created_at=pilot.now(),
            expires_at=pilot.now() + timedelta(hours=8),
        )
    )
    grant.accepted_at = grant.accepted_at or pilot.now()
    audit(session, "Signed in", grant, method=method)
    return {"token": raw, "expires": 8 * 3600}


def finish_scopes(session, scopes, secret, method):
    valid = valid_scopes(session, scopes, secret)
    if len(valid) == 1:
        return new_session(session, valid[0][1][0], secret, method)
    if valid:
        return {
            "context": issue_token(
                session,
                "context",
                {"scopes": [item for item, _ in valid], "method": method},
                3,
            ),
            "scopes": [
                {
                    "id": linked[0].id,
                    "label": f"{linked[1].name} · {'MAH' if linked[0].role == 'mah' else 'End User'}",
                }
                for _, linked in valid
            ],
        }
    return None


def deliver_magic(sessions, secret, raw):
    # Secrets exist only in memory until delivery; requests remain neutral on error.
    with sessions() as session:
        row = session.get(AlertDeskLoginToken, pilot.digest(raw))
        if not row or row.expires_at <= pilot.now():
            return
        valid = valid_scopes(session, row.data["scopes"], secret)
        if not valid:
            return
        email = valid[0][1][2]
        grant_id = valid[0][1][0].id
    try:
        pilot_mail.send_signin(email, raw)
        kind = "Sign-in mail accepted"
    except (OSError, ValueError):
        kind = "Sign-in mail unconfirmed"
    with sessions() as session, session.begin():
        audit(session, kind, session.get(AlertDeskAccess, grant_id))


def install(app, sessions, secret):
    def current(request, session, *, lock=False):
        raw = request.headers.get("x-case-session", "")
        linked = resolve_session(session, raw, secret, lock=lock)
        if not linked:
            raise HTTPException(404, "Sign in to Alert Desk.")
        return raw, linked[0]

    @app.post("/access/login/magic")
    def request_magic(body: LoginCommand, background: BackgroundTasks):
        email = body.email.casefold()
        raw = None
        try:
            with sessions() as session, session.begin():
                prune(session)
                allowed = budget(session, secret, "magic-global", limit=60, minutes=1)
                allowed = (
                    budget(session, secret, "magic:" + email, limit=3, minutes=15)
                    and allowed
                )
                if allowed and audience.deliverable(email):
                    scopes = scopes_for_email(session, email, secret)
                    if scopes:
                        raw = issue_token(session, "magic", {"scopes": scopes}, 15)
                        audit(
                            session,
                            "Sign-in link requested",
                            session.get(AlertDeskAccess, scopes[0]["id"]),
                        )
        except IntegrityError:
            pass  # Concurrent first request is safe to suppress; never reveal membership.
        if raw:
            background.add_task(deliver_magic, sessions, secret, raw)
        return {"message": NEUTRAL}

    @app.post("/access/login/consume")
    def consume_magic(body: LoginCommand):
        result = None
        with sessions() as session, session.begin():
            data = take_token(session, body.token, "magic")
            if data:
                result = finish_scopes(session, data["scopes"], secret, "magic")
        if not result:
            raise HTTPException(
                403, "This sign-in link is invalid or has expired. Request a new link."
            )
        return result

    @app.post("/access/login/scope")
    def choose_scope(body: LoginCommand):
        result = None
        with sessions() as session, session.begin():
            data = take_token(session, body.token, "context")
            if data:
                scopes = [item for item in data["scopes"] if item["id"] == body.scope]
                result = finish_scopes(session, scopes, secret, data["method"])
        if not result:
            raise HTTPException(403, "Start a new sign-in request.")
        return result

    @app.post("/access/login/options")
    def signin_options(body: LoginCommand):
        with sessions() as session, session.begin():
            prune(session)
            if not budget(
                session, secret, "passkey-global", limit=120, minutes=1
            ) or not budget(
                session, secret, "passkey:" + body.email.casefold(), limit=10, minutes=5
            ):
                raise HTTPException(
                    429, "Wait before starting another passkey request."
                )
            challenge = secrets.token_bytes(32)
            raw = issue_token(
                session,
                "signin",
                {
                    "email": keyed(secret, "email:" + body.email.casefold()),
                    "challenge": bytes_to_base64url(challenge),
                },
                3,
            )
            options = generate_authentication_options(
                rp_id=urlsplit(mail_origin()).hostname,
                challenge=challenge,
                user_verification=UV,
            )
        return {"challenge_token": raw, "options": json.loads(options_to_json(options))}

    @app.post("/access/login/finish")
    def signin_finish(body: LoginCommand):
        result = None
        with sessions() as session, session.begin():
            data = take_token(session, body.token, "signin")
            try:
                if not data or not body.credential:
                    raise ValueError()
                cid = base64url_to_bytes(body.credential.get("id", ""))
                key = session.get(
                    AlertDeskParticipantPasskey,
                    sha256(cid).hexdigest(),
                    with_for_update=True,
                )
                linked = (
                    eligible(session, key.access_id, secret, key.binding, lock=True)
                    if key and not key.revoked_at
                    else None
                )
                if not linked or not hmac.compare_digest(
                    data["email"],
                    keyed(secret, "email:" + linked[2].strip().casefold()),
                ):
                    raise ValueError()
                handle = body.credential.get("response", {}).get("userHandle")
                if handle is not None and base64url_to_bytes(handle) != bytes.fromhex(
                    key.binding
                ):
                    raise ValueError()
                verified = verify_authentication_response(
                    credential=body.credential,
                    expected_challenge=base64url_to_bytes(data["challenge"]),
                    expected_rp_id=urlsplit(mail_origin()).hostname,
                    expected_origin=mail_origin(),
                    require_user_verification=True,
                    credential_public_key=base64url_to_bytes(key.public_key),
                    credential_current_sign_count=key.sign_count,
                )
                key.sign_count, key.last_used_at = verified.new_sign_count, pilot.now()
                result = new_session(session, linked[0], secret, "passkey")
            except (WebAuthnException, ValueError, TypeError, AttributeError):
                audit(session, "Passkey sign-in refused")
        if not result:
            raise HTTPException(
                403, "Passkey verification failed. Try again or request a sign-in link."
            )
        return result

    @app.get("/access/login/account")
    def account(request: Request):
        with sessions() as session:
            raw, grant = current(request, session)
            crm, email = access.membership(session, grant)
            keys = session.scalars(
                select(AlertDeskParticipantPasskey)
                .where(
                    AlertDeskParticipantPasskey.access_id == grant.id,
                    AlertDeskParticipantPasskey.binding == binding(secret, grant),
                    AlertDeskParticipantPasskey.revoked_at.is_(None),
                )
                .order_by(AlertDeskParticipantPasskey.created_at)
            )
            return {
                "email": email, "organisation": crm.name, "role": grant.role,
                "can_manage": recently_verified(session, raw, grant),
                "keys": [
                    {
                        "id": key.id,
                        "created_at": key.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "last_used_at": key.last_used_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                        if key.last_used_at
                        else None,
                    }
                    for key in keys
                ]
            }

    @app.post("/access/login/register-options")
    def register_options(request: Request):
        with sessions() as session, session.begin():
            raw, grant = current(request, session, lock=True)
            fresh(session, raw, grant)
            if not budget(session, secret, f"register:{grant.id}", limit=5, minutes=10):
                raise HTTPException(429, "Wait before registering another passkey.")
            linked = access.membership(session, grant)
            keys = session.scalars(
                select(AlertDeskParticipantPasskey).where(
                    AlertDeskParticipantPasskey.access_id == grant.id,
                    AlertDeskParticipantPasskey.revoked_at.is_(None),
                    AlertDeskParticipantPasskey.binding == binding(secret, grant),
                )
            ).all()
            if len(keys) >= 10:
                raise HTTPException(
                    409, "Revoke an unused passkey before adding another."
                )
            challenge = secrets.token_bytes(32)
            options = generate_registration_options(
                rp_id=urlsplit(mail_origin()).hostname,
                rp_name="SMVS Alert Desk",
                user_name=linked[1],
                user_display_name=f"{linked[0].name} · {grant.role}",
                user_id=bytes.fromhex(binding(secret, grant)),
                challenge=challenge,
                authenticator_selection=AuthenticatorSelectionCriteria(
                    resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UV
                ),
                exclude_credentials=[
                    PublicKeyCredentialDescriptor(
                        id=base64url_to_bytes(key.credential_id)
                    )
                    for key in keys
                ],
            )
            token = issue_token(
                session,
                "register",
                {
                    "session": pilot.digest(raw),
                    "access": grant.id,
                    "binding": binding(secret, grant),
                    "challenge": bytes_to_base64url(challenge),
                },
                3,
            )
        return {
            "challenge_token": token,
            "options": json.loads(options_to_json(options)),
        }

    @app.post("/access/login/register-finish")
    def register_finish(request: Request, body: LoginCommand):
        okay = False
        try:
            with sessions() as session, session.begin():
                raw, grant = current(request, session, lock=True)
                fresh(session, raw, grant)
                data = take_token(session, body.token, "register")
                try:
                    if (
                        not data
                        or data["session"] != pilot.digest(raw)
                        or data["access"] != grant.id
                        or data["binding"] != binding(secret, grant)
                    ):
                        raise ValueError()
                    count = session.scalar(
                        select(func.count())
                        .select_from(AlertDeskParticipantPasskey)
                        .where(
                            AlertDeskParticipantPasskey.access_id == grant.id,
                            AlertDeskParticipantPasskey.binding
                            == binding(secret, grant),
                            AlertDeskParticipantPasskey.revoked_at.is_(None),
                        )
                    )
                    if count >= 10:
                        raise ValueError()
                    verified = verify_registration_response(
                        credential=body.credential,
                        expected_challenge=base64url_to_bytes(data["challenge"]),
                        expected_rp_id=urlsplit(mail_origin()).hostname,
                        expected_origin=mail_origin(),
                        require_user_verification=True,
                    )
                    key = AlertDeskParticipantPasskey(
                        id=sha256(verified.credential_id).hexdigest(),
                        access_id=grant.id,
                        binding=binding(secret, grant),
                        credential_id=bytes_to_base64url(verified.credential_id),
                        public_key=bytes_to_base64url(verified.credential_public_key),
                        sign_count=verified.sign_count,
                        created_at=pilot.now(),
                    )
                    session.add(key)
                    session.flush()
                    audit(session, "Passkey registered", grant, passkey=key.id)
                    okay = True
                except (WebAuthnException, ValueError, TypeError, AttributeError):
                    audit(session, "Passkey registration refused", grant)
        except IntegrityError:
            # A duplicated authenticator must never be transferred to another scope.
            with sessions() as session, session.begin():
                take_token(session, body.token, "register")
                audit(session, "Passkey registration refused")
        if not okay:
            raise HTTPException(
                403, "Passkey registration failed. Start a new request."
            )
        return {"registered": True}

    @app.post("/access/login/revoke")
    def revoke(request: Request, body: LoginCommand):
        with sessions() as session, session.begin():
            raw, grant = current(request, session, lock=True)
            fresh(session, raw, grant)
            key = (
                session.get(AlertDeskParticipantPasskey, body.key, with_for_update=True)
                if body.key
                else None
            )
            if (
                not key
                or key.access_id != grant.id
                or key.binding != binding(secret, grant)
                or key.revoked_at
            ):
                raise HTTPException(404, "Passkey unavailable.")
            key.revoked_at = pilot.now()
            for row in session.scalars(
                select(AlertDeskParticipantSession).where(
                    AlertDeskParticipantSession.access_id == grant.id
                )
            ):
                row.revoked_at = pilot.now()
            grant.session_hash = grant.session_expires_at = None
            audit(session, "Passkey revoked", grant, passkey=key.id)
        return {"signed_out": True}

    @app.post("/access/login/logout")
    def logout(request: Request):
        with sessions() as session, session.begin():
            raw, grant = current(request, session, lock=True)
            row = session.get(
                AlertDeskParticipantSession, pilot.digest(raw), with_for_update=True
            )
            if row:
                row.revoked_at = pilot.now()
            else:
                grant.session_hash = grant.session_expires_at = None
            audit(session, "Signed out", grant)
        return {"signed_out": True}
