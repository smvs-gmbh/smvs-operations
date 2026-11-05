"""Retained evidence for repeated A7 state-change operations. All decisions remain operator actions."""

from sqlalchemy import select

from app.domain.models import NMVSException, PackAuditReport, PackAuditRequest
from app.domain.pack_audit.service import record_signature
from app.domain.pack_audit.timeline import summarize

OPERATIONS = {
    "EXPORTED": ("Export", "Exported"),
    "DESTROYED": ("Destroy", "Destroyed"),
}


def operation_for(record):
    if record.error_code == "A7":
        return OPERATIONS.get(record.evidence.get("attemptedOperation"))
    return None


def batch_identity(record):
    batch = record.stored_batch or record.provided_batch
    if not (record.product_code_scheme and record.product_code and batch):
        return None
    return (
        record.source_namespace,
        record.product_code_scheme,
        record.product_code,
        batch,
    )


def repeat_sequence(session, record):
    operation = operation_for(record)
    if not operation:
        return None
    label, target_state = operation
    try:
        signature = record_signature(record)
    except ValueError:
        return None
    report = session.scalar(
        select(PackAuditReport)
        .join(PackAuditRequest, PackAuditRequest.latest_report_id == PackAuditReport.id)
        .where(
            PackAuditRequest.signature_key == signature,
            PackAuditReport.signature_key == signature,
            PackAuditReport.source_namespace == record.source_namespace,
            PackAuditReport.is_example == 0,
        )
    )
    if not report:
        return None
    timeline = summarize(
        report.events_json,
        alert_id=record.unique_alert_id,
        transaction_id=record.transaction_id,
    )
    repeat = timeline["selected"]
    previous = timeline["last_change"]
    if not (
        repeat
        and previous
        and repeat["kind"] == "error"
        and "A7" in repeat["codes"]
        and repeat["operation"] == previous["operation"] == label
        and any(
            item["raw"].get("Event Name")
            in ("IntermarketSuccessfulPackStateChange", "PackStateChangeSuccessful")
            for item in previous["items"]
        )
        and (
            not record.transaction_id
            or repeat["transaction_id"] == record.transaction_id
        )
        and previous["before"] == "Active"
        and previous["actual"] == repeat["before"] == repeat["actual"] == target_state
        and repeat["transaction_id"]
        and previous["transaction_id"]
        and repeat["market"] == previous["market"] == record.source_market
        and repeat["location"] == previous["location"] == record.source_location_id
        and record.source_market
        and record.source_location_id
        and not timeline["unknown_times"]
    ):
        return None
    # A failed or ambiguous intervening state observation must not hide a contradiction.
    for group in timeline["groups"]:
        if previous["at"] < group["at"] < repeat["at"] and any(
            group[field] not in (None, target_state) for field in ("before", "actual")
        ):
            return None
    return {"report_id": report.id, "previous": previous, "repeat": repeat}


def history(session, record):
    if not record.source_market or not record.source_location_id:
        return None
    rows = session.scalars(
        select(NMVSException).where(
            NMVSException.source_namespace == record.source_namespace,
            NMVSException.source_market == record.source_market,
            NMVSException.source_location_id == record.source_location_id,
            NMVSException.error_code == "A7",
        )
    )
    operation = operation_for(record)
    identity = batch_identity(record)
    scope = (record.source_namespace, record.source_market, record.source_location_id)
    packs, batch_packs, batch_alerts, dates = set(), set(), [], []
    for row in rows:
        if (
            row.source_namespace,
            row.source_market,
            row.source_location_id,
        ) != scope or operation_for(row) != operation:
            continue
        if row.serial_number:
            packs.add((row.product_code_scheme, row.product_code, row.serial_number))
        if row.alert_at:
            dates.append(row.alert_at)
        if identity and batch_identity(row) == identity:
            batch_alerts.append(row.id)
            if row.serial_number:
                batch_packs.add(row.serial_number)
    return {
        "packs": len(packs),
        "batch_packs": len(batch_packs),
        "batch_alerts": len(batch_alerts),
        "first": min(dates) if dates else None,
        "last": max(dates) if dates else None,
    }
