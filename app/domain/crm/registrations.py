"""Internal registration state machine. No NMVS write operation is implemented."""

import csv
import hashlib
import io
import json
import uuid
from datetime import timedelta

from sqlalchemy import func, or_, select

from app.domain.models import (
    CRMContact,
    CRMEndUser,
    EndUserRegistration,
    RegistrationEvent,
)
from app.integration.artifacts.storage import utcnow
from app.registration.crypto import decrypt, encrypt
from app.registration.schema import SECRET_FIELDS, timestamp, validate_values

STATUSES = {
    "awaiting_email": "Awaiting email confirmation",
    "needs_review": "Needs review",
    "ready_nmvs": "Ready for NMVS",
    "nmvs_created": "NMVS created",
    "rejected": "Rejected",
    "expired": "Expired before import",
}


def event(session, row, actor, action, note=None):
    actor_id, label = actor if isinstance(actor, tuple) else (None, actor)
    session.add(
        RegistrationEvent(
            registration_id=row.id,
            occurred_at=utcnow(),
            actor=label,
            actor_user_id=actor_id,
            action=action,
            note=note,
        )
    )


def purge_expired(session):
    for row in session.scalars(
        select(EndUserRegistration)
        .where(
            EndUserRegistration.security_expires_at <= utcnow(),
            EndUserRegistration.security_ciphertext.is_not(None),
        )
        .with_for_update()
    ):
        row.security_ciphertext = None
        event(session, row, "System", "security_data_expired")


def import_intake(session, data, key):
    identifier = str(uuid.UUID(data["id"]))
    revision = data["revision"]
    if not isinstance(revision, int) or not 1 <= revision <= 100:
        raise ValueError("Invalid registration revision.")
    row = session.scalar(
        select(EndUserRegistration)
        .where(EndUserRegistration.intake_id == identifier)
        .with_for_update()
    )
    mail_status = data.get("mail_status", "unknown")
    if mail_status not in {
        "queued",
        "sending",
        "accepted",
        "uncertain",
        "failed",
        "expired",
        "unknown",
    }:
        raise ValueError("Invalid mail status.")
    if row and row.intake_revision >= revision:
        return row
    values = data["values"]
    confirmed = timestamp(data["confirmed_at"]) if data.get("confirmed_at") else None
    expiry = timestamp(data["expires_at"])
    submitted = timestamp(data["submitted_at"])
    if not row:
        if values is None:
            row = EndUserRegistration(
                intake_id=identifier,
                intake_revision=revision,
                submitted_email="",
                submitted_at=submitted,
                received_at=utcnow(),
                status="expired",
                security_expires_at=expiry,
            )
            session.add(row)
            session.flush()
            event(session, row, "Tally intake", "expired_before_import")
            return row
        validate_values(values)
        expiry = min(
            expiry, submitted + timedelta(days=7), utcnow() + timedelta(days=7)
        )
        # Each source submission creates an isolated provisional CRM record. No name/email merge.
        function_csv = io.StringIO()
        csv.writer(function_csv).writerow([values["function"]])
        contact = CRMContact(
            airtable_id="registration:" + identifier,
            label=values["first_name"] + " " + values["last_name"],
            function=function_csv.getvalue().rstrip("\r\n"),
            profile={
                k: values[k] for k in ("first_name", "last_name", "email", "phone")
            }
            | {"registration_pending": True},
        )
        session.add(contact)
        session.flush()
        profile = {
            k: v
            for k, v in values.items()
            if k not in SECRET_FIELDS
            and k not in ("first_name", "last_name", "function")
        }
        profile["spoc_ids"] = [contact.id]
        user = CRMEndUser(name=values["name"], profile=profile)
        session.add(user)
        session.flush()
        row = EndUserRegistration(
            intake_id=identifier,
            intake_revision=revision,
            end_user_id=user.id,
            contact_id=contact.id,
            submitted_email=values["email"],
            confirmation_mail_status=mail_status,
            submitted_at=submitted,
            received_at=utcnow(),
            confirmed_at=confirmed,
            status="needs_review" if confirmed else "awaiting_email",
            security_expires_at=expiry,
            security_ciphertext=encrypt(key, {k: values[k] for k in SECRET_FIELDS})
            if expiry > utcnow()
            else None,
        )
        session.add(row)
        session.flush()
        user.profile = profile | {"registration_id": row.id}
        event(session, row, "Tally intake", "received")
        if confirmed:
            event(session, row, "Email confirmation", "email_confirmed")
    else:
        row.intake_revision = revision
        row.confirmation_mail_status = mail_status
        if confirmed and row.confirmed_at is None:
            row.confirmed_at = confirmed
            if row.status == "awaiting_email":
                row.status = "needs_review"
            event(session, row, "Email confirmation", "email_confirmed")
    purge_expired(session)
    return row


def duplicate_candidates(session, row):
    user = session.get(CRMEndUser, row.end_user_id)
    if not user:
        return []
    gln = (user.profile or {}).get("gln")
    conditions = [func.lower(CRMEndUser.name) == user.name.lower()]
    if gln:
        conditions.append(CRMEndUser.profile["gln"].as_string() == gln)
    return session.scalars(
        select(CRMEndUser)
        .where(
            CRMEndUser.id != user.id, CRMEndUser.archived_at.is_(None), or_(*conditions)
        )
        .limit(20)
    ).all()


def review_hash(user, contact):
    return hashlib.sha256(
        json.dumps(
            {
                "name": user.name,
                "profile": user.profile,
                "contact": contact.profile,
                "function": contact.function,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def act(session, row, command, actor, note="", nmvs_id="", duplicates_checked=False):
    note = note.strip()
    if len(note) > 2000:
        raise ValueError("Use a review note of up to 2000 characters.")
    user = session.get(CRMEndUser, row.end_user_id) if row.end_user_id else None
    contact = session.get(CRMContact, row.contact_id) if row.contact_id else None
    if command in ("approve", "nmvs_created") and (
        not user or user.archived_at or not contact or contact.archived_at
    ):
        raise ValueError("Restore the provisional CRM records before continuing.")
    if (
        command in ("approve", "nmvs_created")
        and (contact.profile or {}).get("email", "").casefold()
        != row.submitted_email.casefold()
    ):
        raise ValueError(
            "The contact email differs from the confirmed address. A new confirmation is required."
        )
    if command == "approve":
        if row.status != "needs_review" or not row.confirmed_at:
            raise ValueError(
                "Confirm the email address before approving this registration."
            )
        if duplicate_candidates(session, row) and not duplicates_checked:
            raise ValueError("Review the possible duplicate CRM records first.")
        row.status = "ready_nmvs"
        contact.profile = (contact.profile or {}) | {"registration_pending": False}
        row.reviewed_hash = review_hash(user, contact)
        row.reviewed_at = utcnow()
        row.reviewed_by = actor[1] if isinstance(actor, tuple) else actor
        row.review_note = note
        event(session, row, actor, "review_approved", note)
    elif command == "reject":
        if (
            row.status not in ("awaiting_email", "needs_review", "ready_nmvs")
            or not note
        ):
            raise ValueError("Enter a reason to reject this pending registration.")
        row.status = "rejected"
        row.review_note = note
        row.reviewed_at = utcnow()
        row.reviewed_by = actor[1] if isinstance(actor, tuple) else actor
        row.security_ciphertext = None
        user = session.get(CRMEndUser, row.end_user_id)
        if user:
            user.archived_at = utcnow()
        contact = session.get(CRMContact, row.contact_id)
        if contact:
            contact.archived_at = utcnow()
        event(session, row, actor, "rejected", note)
    elif command == "nmvs_created":
        if row.reviewed_hash != review_hash(user, contact):
            raise ValueError(
                "CRM details changed after approval. Reopen and review this registration again."
            )
        nmvs_id = nmvs_id.strip()
        if (
            row.status != "ready_nmvs"
            or not nmvs_id
            or len(nmvs_id) > 100
            or any(ord(c) < 32 for c in nmvs_id)
        ):
            raise ValueError("Approve the review and enter the NMVS organisation ID.")
        row.status = "nmvs_created"
        row.nmvs_organisation_id = nmvs_id
        row.nmvs_created_at = utcnow()
        row.security_ciphertext = None
        user = session.get(CRMEndUser, row.end_user_id)
        if user:
            user.profile = (user.profile or {}) | {"nmvs_registration_id": nmvs_id}
        event(session, row, actor, "nmvs_creation_recorded", nmvs_id)
    elif command == "reopen":
        if row.status not in ("ready_nmvs", "nmvs_created", "rejected") or not note:
            raise ValueError("Enter a reason to reopen a reviewed registration.")
        row.status = "needs_review" if row.confirmed_at else "awaiting_email"
        if contact:
            contact.profile = (contact.profile or {}) | {"registration_pending": True}
        row.reviewed_at = row.reviewed_by = None
        row.review_note = note
        if row.end_user_id:
            user = session.get(CRMEndUser, row.end_user_id)
            if user:
                user.archived_at = None
        if row.contact_id:
            contact = session.get(CRMContact, row.contact_id)
            if contact:
                contact.archived_at = None
        event(session, row, actor, "review_reopened", note)
    else:
        raise ValueError("Choose a valid registration action.")


def security_data(session, row, key, actor):
    if (
        row.status != "ready_nmvs"
        or not row.security_ciphertext
        or row.security_expires_at <= utcnow()
    ):
        raise ValueError(
            "Security data is unavailable or expired. Request it securely from the registrant if needed."
        )
    values = decrypt(key, row.security_ciphertext)
    event(session, row, actor, "security_data_viewed")
    return values
