"""Durable registration intake, confirmation and bounded outbound exchange."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from app.registration.crypto import decrypt, encrypt
from app.registration.models import IntakeRegistration
from app.registration.schema import parse_submission


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def receive(session, payload, key, ttl_days=7, *, model=IntakeRegistration):
    event, submission, submitted, values = parse_submission(payload)
    existing = session.scalar(
        select(model)
        .where(
            or_(
                model.event_id == event,
                model.submission_id == submission,
            )
        )
        .with_for_update()
    )
    if existing:
        return existing, False
    received = now()
    if not 1 <= ttl_days <= 30:
        raise ValueError("Choose a security-data lifetime of 1–30 days.")
    raw = secrets.token_urlsafe(32)
    row = model(
        id=str(uuid.uuid4()),
        event_id=event,
        submission_id=submission,
        submitted_at=submitted,
        received_at=received,
        expires_at=received + timedelta(days=ttl_days),
        payload_ciphertext=encrypt(key, values),
        token_digest=token_hash(raw),
        token_ciphertext=encrypt(key, {"token": raw}),
        token_expires_at=received + timedelta(hours=24),
        revision=1,
        acknowledged_revision=0,
        mail_status="queued",
        mail_attempts=0,
    )
    session.add(row)
    session.flush()
    return row, True


def confirm(session, token, *, model=IntakeRegistration):
    if not isinstance(token, str) or len(token) != 43:
        return False
    row = session.scalar(
        select(model)
        .where(
            model.token_digest == token_hash(token),
            model.token_expires_at > now(),
            model.expires_at > now(),
        )
        .with_for_update()
    )
    if row is None or row.confirmed_at is not None:
        return False
    row.confirmed_at = now()
    row.token_digest = row.token_ciphertext = None
    row.revision += 1
    return True


def purge(session, *, model=IntakeRegistration):
    rows = session.scalars(
        select(model)
        .where(
            model.expires_at <= now(),
            model.payload_ciphertext.is_not(None),
        )
        .with_for_update()
    )
    for row in rows:
        row.payload_ciphertext = row.token_ciphertext = row.token_digest = None
        row.mail_status = "expired"
        row.revision += 1


def exchange_rows(session, key, *, model=IntakeRegistration):
    purge(session, model=model)
    rows = session.scalars(
        select(model)
        .where(model.revision > model.acknowledged_revision)
        .order_by(model.received_at, model.id)
        .limit(100)
    )
    result = []
    for row in rows:
        # The exchange returns an explicit allowlist, never ORM/raw webhook serialisation.
        result.append(
            {
                "id": row.id,
                "revision": row.revision,
                "mail_status": row.mail_status,
                "submitted_at": row.submitted_at.isoformat() + "Z",
                "confirmed_at": row.confirmed_at.isoformat() + "Z"
                if row.confirmed_at
                else None,
                "expires_at": row.expires_at.isoformat() + "Z",
                "values": decrypt(key, row.payload_ciphertext)
                if row.payload_ciphertext
                else None,
            }
        )
    return result


def acknowledge(session, identifier, revision, *, model=IntakeRegistration):
    row = session.get(model, identifier, with_for_update=True)
    if (
        row is None
        or not isinstance(revision, int)
        or revision < 1
        or revision > row.revision
    ):
        raise ValueError("Invalid acknowledgement.")
    row.acknowledged_revision = max(row.acknowledged_revision, revision)
    if row.confirmed_at and revision == row.revision:
        row.payload_ciphertext = row.token_ciphertext = row.token_digest = None


def resend(session, identifier, revision, key, *, model=IntakeRegistration):
    row = session.get(model, identifier, with_for_update=True)
    if (
        not row
        or row.revision != revision
        or row.confirmed_at
        or not row.payload_ciphertext
        or row.expires_at <= now()
    ):
        raise ValueError(
            "This confirmation cannot be resent. Synchronise the registration first."
        )
    if row.mail_attempted_at and now() - row.mail_attempted_at < timedelta(minutes=5):
        raise ValueError(
            "Wait five minutes before requesting another confirmation email."
        )
    raw = secrets.token_urlsafe(32)
    row.token_digest = token_hash(raw)
    row.token_ciphertext = encrypt(key, {"token": raw})
    row.token_expires_at = min(now() + timedelta(hours=24), row.expires_at)
    row.mail_status = "queued"
    row.mail_attempted_at = now()
    row.revision += 1
