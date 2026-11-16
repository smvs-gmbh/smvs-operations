"""Shared investigation responsibility and closure in Operations."""

import re
from hashlib import sha256

from sqlalchemy import select

from app.domain.models import (
    AlertDeskEvent,
    AlertDeskGrant,
    ExceptionReview,
    LocalLocation,
    LocalOrganisation,
    NMVSException,
)

ORIGINS = {
    "end_user": "End User",
    "mah": "MAH",
    "both": "Both",
    "nmvs": "NMVS",
    "other": "Other",
    "undetermined": "Undetermined",
}
ROLES = {"end_user": "End User", "mah": "MAH"}
CLOSED_BASIS = "shared_investigation"


def confirmed_location(organisation, location, record):
    return bool(
        organisation
        and location
        and organisation.is_observed
        and location.is_observed
        and organisation.source_namespace
        == location.source_namespace
        == record.source_namespace
        and organisation.source_organisation_id == record.organisation_id
        and location.source_location_id == record.source_location_id
        and location.organisation_id == organisation.id
    )


def responsibility(session, record):
    market = record.source_market or ""
    if market not in {"CH", "LI"}:
        return (
            "foreign"
            if re.fullmatch(r"[A-Z]{2}", market)
            and market not in {"EU", "XX"}
            and record.source_location_id
            else "unconfirmed"
        )
    if market == "CH" and record.is_intermarket == 0:
        return "local"
    if market == "LI" and record.is_intermarket != 1:
        return "unconfirmed"
    if record.is_intermarket != 1:
        return "unconfirmed"

    rows = session.execute(
        select(LocalOrganisation, LocalLocation)
        .join(LocalLocation, LocalLocation.organisation_id == LocalOrganisation.id)
        .where(
            LocalLocation.source_location_id == record.source_location_id,
            LocalOrganisation.source_organisation_id == record.organisation_id,
            LocalLocation.source_namespace == record.source_namespace,
            LocalOrganisation.source_namespace == record.source_namespace,
            LocalLocation.is_observed == 1,
            LocalOrganisation.is_observed == 1,
        )
        .limit(2)
    ).all()
    if len(rows) == 1 and confirmed_location(*rows[0], record):
        return "liechtenstein" if market == "LI" else "local"
    return "unconfirmed"


def origin_options(scope):
    if scope == "liechtenstein":
        return {key: ORIGINS[key] for key in ("end_user", "undetermined")}
    return ORIGINS


def participant_findings(session, identifiers, *, lock=False):
    statement = (
        select(
            AlertDeskGrant.exception_id,
            AlertDeskGrant.publication["audience"].as_string(),
            AlertDeskEvent,
        )
        .join(AlertDeskEvent, AlertDeskEvent.grant_id == AlertDeskGrant.id)
        .join(NMVSException, NMVSException.id == AlertDeskGrant.exception_id)
        .where(
            AlertDeskGrant.exception_id.in_(identifiers),
            AlertDeskGrant.source_version == NMVSException.payload_hash,
            AlertDeskEvent.kind == "Findings submitted",
        )
        .order_by(AlertDeskEvent.id.desc())
    )
    findings = {}
    for identifier, role, event in session.execute(
        statement.with_for_update() if lock else statement
    ):
        if role in ROLES:
            findings.setdefault(identifier, {}).setdefault(role, event)
    return findings


def applicable_findings(findings, scope):
    return {
        role: event
        for role, event in findings.items()
        if role != "mah" or scope != "liechtenstein"
    }


def fingerprint(rows, findings, scope):
    state = [
        (
            record.id,
            record.payload_hash,
            review.version if review else 0,
            sorted(
                (role, event.id)
                for role, event in applicable_findings(
                    findings.get(record.id, {}), scope
                ).items()
            ),
        )
        for record, review in rows
    ]
    return sha256(repr((scope, state)).encode()).hexdigest()


def is_closed(review, record):
    return bool(
        resolved_for_source(review, record)
        and (review.resolution or {}).get("basis") == CLOSED_BASIS
    )


def resolved_for_source(review, record):
    return bool(
        review
        and review.status == "resolved"
        and review.basis_payload_hash == record.payload_hash
    )


def closed_condition():
    return (
        select(ExceptionReview.exception_id)
        .where(
            ExceptionReview.exception_id == NMVSException.id,
            ExceptionReview.status == "resolved",
            ExceptionReview.basis_payload_hash == NMVSException.payload_hash,
            ExceptionReview.resolution["basis"].as_string() == CLOSED_BASIS,
        )
        .correlate(NMVSException)
        .exists()
    )


def batch_rows(session, record, *, lock=False):
    fields = (
        "source_namespace",
        "product_code_scheme",
        "product_code",
        "error_code",
        "source_market",
        "source_location_id",
        "organisation_id",
        "business_process",
        "is_intermarket",
    )
    operation = (record.evidence or {}).get("attemptedOperation")
    if not all(
        (
            record.product_code_scheme,
            record.product_code,
            record.error_code,
            record.source_location_id,
            operation,
            record.provided_batch or record.stored_batch,
        )
    ):
        return []
    statement = (
        select(NMVSException)
        .where(
            *(
                getattr(NMVSException, field) == getattr(record, field)
                for field in fields
            ),
            NMVSException.evidence["attemptedOperation"].as_string() == operation,
        )
        .order_by(NMVSException.id)
    )
    if lock:
        statement = statement.with_for_update().execution_options(
            populate_existing=True
        )
    records = [
        item
        for item in session.scalars(statement)
        if (item.provided_batch or item.stored_batch)
        and all(getattr(item, field) == getattr(record, field) for field in fields)
        and (item.evidence or {}).get("attemptedOperation") == operation
    ]
    query = select(ExceptionReview).where(
        ExceptionReview.exception_id.in_([item.id for item in records])
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    reviews = {review.exception_id: review for review in session.scalars(query)}
    return [(item, reviews.get(item.id)) for item in records]


def batch_groups(rows):
    groups = {}
    for record, review in rows:
        if review and (
            resolved_for_source(review, record)
            or review.status == "to_do"
            or review.next_action.strip()
            or review.due_date
        ):
            continue
        groups.setdefault((record.provided_batch, record.stored_batch), []).append(
            (record, review)
        )
    return groups
