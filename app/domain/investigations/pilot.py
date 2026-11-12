"""Private grant and audit persistence for the local A3 pilot."""

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select

from app.domain.investigations import audience
from app.domain.investigations.preview import OPERATIONS, utc
from app.domain.models import (
    AlertDeskEvent,
    AlertDeskGrant,
    LocalLocation,
    LocalOrganisation,
    NMVSException,
    PackAuditReport,
)
from app.domain.pack_audit.timeline import summarize


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def in_scope(record, organisation, location):
    return bool(
        record
        and record.error_code in {"A2", "A3"}
        and record.source_market in {"CH", "LI"}
        and record.is_intermarket == 0
        and (
            record.provided_batch if record.error_code == "A2" else record.serial_number
        )
        and organisation
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


def investigation_for(record, organisation, location, role):
    if record.error_code == "A7":
        return "mah_a7" if role == "mah" else "end_user_a7"
    if in_scope(record, organisation, location):
        return record.error_code.lower()
    return None


def append_event(session, grant, kind, *, actor=None, data=None, key=None):
    session.add(
        AlertDeskEvent(
            grant_id=grant.id,
            actor_id=actor,
            kind=kind,
            occurred_at=now(),
            data=data or {},
            submission_key=key,
        )
    )


def a7_evidence(prechecks, role):
    repeat = prechecks["repeat"] if role == "end_user" else None
    if not repeat:
        return {
            "summary": "The requested state was already recorded for this pack.",
            "detail": "The alert records a rejected operation. The earlier transaction has not been established in this view.",
        }, None

    previous, rejected = repeat["previous"], repeat["repeat"]
    operation, state = rejected["operation"], rejected["actual"]
    intelligence = {
        "summary": f"The pack was already marked {state.lower()}. The same location submitted another {operation} request.",
        "detail": "The Pack Audit Trail links the earlier successful state change and the rejected repeat to the same reported location.",
    }
    audit = {
        "captured_at": utc(prechecks["report_captured_at"])
        if prechecks["report_id"] == repeat["report_id"]
        else None,
        "events": [
            {"at": utc(previous["at"]), "title": f"Active → {state}"},
            {"at": utc(rejected["at"]), "title": f"Repeat {operation} rejected · A7"},
        ],
    }
    return intelligence, audit


def participant_intelligence(prechecks):
    results = {item["code"]: item["result"] for item in prechecks["checks"]}
    length = {
        "consistent": "The submitted serial length matches the batch reference.",
        "discrepancy": "The submitted serial length differs from the batch reference.",
    }.get(results.get("serial-length"))
    if not prechecks["snapshot_date"]:
        return {"summary": "No batch reference is available for this product."}
    if results.get("snapshot-batch") == "observed":
        summary = length or "The batch was found in the records checked."
    else:
        summary = "No match for this batch in the records checked."
    return {
        "summary": summary,
        "source_date": prechecks["snapshot_date"],
        "detail": "The available batch records do not establish the upload status of this serial.",
    }


def participant_report(session, record, report_id):
    report = session.get(PackAuditReport, report_id)
    timeline = summarize(
        report.events_json,
        alert_id=record.unique_alert_id,
        transaction_id=record.transaction_id,
    )
    titles = {
        "created": "Pack created",
        "change": "Pack state changed",
        "error": "Operation rejected",
    }
    events = [
        {"at": utc(row["at"]), "title": titles[row["kind"]]}
        for row in timeline["relevant"]
        if row["kind"] in titles
        and (
            row["kind"] == "created"
            or row["matched"]
            or row["location"] == record.source_location_id
        )
    ]
    return {"captured_at": utc(report.captured_at), "events": events[-12:]}


def publication(
    session,
    record,
    organisation,
    location,
    view,
    prechecks,
    *,
    share_report=False,
    role="end_user",
):
    evidence = record.evidence or {}
    intelligence, audit = (
        a7_evidence(prechecks, role)
        if record.error_code == "A7"
        else (participant_intelligence(prechecks), None)
    )
    if not audit and share_report and prechecks["report_id"] and role == "end_user":
        audit = participant_report(session, record, prechecks["report_id"])
    review = view["review"]
    locally_resolved = bool(
        review
        and review.status == "resolved"
        and review.basis_payload_hash == record.payload_hash
    )
    return {
        "audience": role,
        "alert": record.unique_alert_id,
        "product": view["name"],
        "mah": view["holder"],
        "product_code": record.gtin14 or record.product_code,
        "batch": record.provided_batch,
        "serial": record.serial_number,
        "operation": OPERATIONS.get(evidence.get("attemptedOperation")),
        "operation_code": evidence.get("operationCode"),
        "organisation": organisation.organisation_name
        if organisation and role == "end_user"
        else view["holder"]
        if role == "mah"
        else None,
        "location": location.location_name if location and role == "end_user" else None,
        "intelligence": intelligence,
        "audit": audit,
        "locally_resolved": locally_resolved,
        "alert_at": utc(record.alert_at) if record.alert_at else None,
    }


def active_grant(session, token, *, invitation=False, lock=False):
    column = AlertDeskGrant.invite_hash if invitation else AlertDeskGrant.session_hash
    query = select(AlertDeskGrant).where(column == digest(token))
    grant = session.scalar(query.with_for_update() if lock else query)
    if not grant or grant.revoked_at or grant.expires_at <= now():
        return None
    record = session.get(NMVSException, grant.exception_id)
    organisation = (
        session.get(LocalOrganisation, grant.organisation_id)
        if grant.organisation_id
        else None
    )
    location = (
        session.get(LocalLocation, grant.location_id) if grant.location_id else None
    )
    if (
        in_scope(record, organisation, location)
        and record.payload_hash == grant.source_version
    ):
        recipient = grant.publication.get("recipient")
        if recipient:
            crm = audience.organisation_for(
                session, record, organisation.id, grant.publication["audience"]
            )
            if (
                not crm
                or crm.id != recipient["organisation"]
                or not any(
                    contact.id == recipient["contact"]
                    and contact.version == recipient["version"]
                    for contact, _ in audience.recipients(session, crm)
                )
            ):
                return None
        return grant
    return None
