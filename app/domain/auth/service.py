"""Internal portal identity and short-lived token handling."""

import re
from datetime import timedelta
from hashlib import sha256
from secrets import token_hex, token_urlsafe
from urllib.parse import urlsplit

from sqlalchemy import delete, select

from app.domain.models import PortalAuthToken, PortalUser
from app.integration.artifacts.storage import utcnow

SESSION_COOKIE = "smvs_portal_session"
CHALLENGE_COOKIE = "smvs_portal_challenge"
SESSION_LIFETIME = timedelta(hours=8)
CHALLENGE_LIFETIME = timedelta(minutes=3)
INVITATION_LIFETIME = timedelta(hours=24)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


def origin_config(settings):
    url = urlsplit(settings.portal_auth_origin)
    local = url.hostname == "localhost"
    if (
        not url.hostname
        or url.username
        or url.password
        or url.path
        or url.query
        or url.fragment
        or (url.scheme != "https" and not (local and url.scheme == "http"))
        or settings.portal_auth_origin != f"{url.scheme}://{url.netloc}"
    ):
        raise ValueError(
            "Set PORTAL_AUTH_ORIGIN to a canonical HTTPS origin or http://localhost:<port>."
        )
    return url.hostname, url.scheme == "https"


def digest(value):
    return sha256(value).hexdigest()


def issue_token(
    session, kind, lifetime, *, user_id=None, challenge=None, invitation_id=None
):
    raw = token_urlsafe(32)
    now = utcnow()
    session.add(
        PortalAuthToken(
            id=digest(raw.encode()),
            kind=kind,
            user_id=user_id,
            challenge=challenge,
            invitation_id=invitation_id,
            created_at=now,
            expires_at=now + lifetime,
        )
    )
    return raw


def get_token(session, raw, kind, *, lock=False):
    if not isinstance(raw, str) or not TOKEN_PATTERN.fullmatch(raw):
        return None
    statement = select(PortalAuthToken).where(
        PortalAuthToken.id == digest(raw.encode()),
        PortalAuthToken.kind == kind,
        PortalAuthToken.expires_at > utcnow(),
    )
    return session.scalar(statement.with_for_update() if lock else statement)


def prune_tokens(session):
    session.execute(
        delete(PortalAuthToken).where(PortalAuthToken.expires_at <= utcnow())
    )


def invite_user(session, email, *, admin, nmvo):
    email = email.strip().lower()
    if (
        not re.fullmatch(r"[^\s@]+@[^\s@]+", email)
        or len(email) > 254
        or not (admin or nmvo)
    ):
        raise ValueError("Enter a valid email and select at least one role.")
    user = PortalUser(
        email=email, handle=token_hex(32), is_admin=int(admin), is_nmvo=int(nmvo)
    )
    session.add(user)
    session.flush()
    return issue_token(session, "invite", INVITATION_LIFETIME, user_id=user.id)


def invitation_url(origin, token):
    return f"{origin}/auth/login#{token}"
