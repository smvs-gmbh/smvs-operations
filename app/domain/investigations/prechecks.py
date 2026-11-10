"""Read-only observations that reduce repeated participant investigation work.

No correction, cause confirmation, report request or resolution happens on read.
"""

import re

from sqlalchemy import select

from app.domain.exceptions import repeat_evidence
from app.domain.investigations.preview import batch_reference
from app.domain.mapping import key
from app.domain.models import (
    Batch,
    CurrentPublication,
    PackAuditReport,
    PackAuditRequest,
    ProductSourceRecord,
)
from app.domain.pack_audit.service import record_signature

VERSION = "investigation-prechecks-1"


def observation(code, label, result, detail):
    return {"code": code, "label": label, "result": result, "detail": detail}


def positive_integer(value):
    text = str(value) if value is not None else ""
    return (
        int(text)
        if re.fullmatch(r"[0-9]{1,3}", text) and 0 < int(text) <= 100
        else None
    )


def identifier_checks(record, batches):
    """Exact values only. Snapshot matches do not establish alert-time truth."""
    checks = []
    provided, stored = record.provided_batch, record.stored_batch
    if provided and stored:
        same = provided == stored
        checks.append(
            observation(
                "batch-comparison",
                "Provided / stored batch",
                "consistent" if same else "discrepancy",
                "The provided and stored batch values are identical."
                if same
                else "The provided and stored batch values differ. Compare with the physical pack; do not replace either value automatically.",
            )
        )
    else:
        checks.append(
            observation(
                "batch-comparison",
                "Provided / stored batch",
                "unknown",
                "One or both batch values are missing.",
            )
        )
    batch = batches.get("provided_batch")
    checks.append(
        observation(
            "snapshot-batch",
            "Provided batch in retained Snapshot",
            "observed" if batch else "unknown",
            "An exact product/batch match is retained. This does not establish contents at alert time."
            if batch
            else "No exact current Snapshot match is available. This does not prove the batch was never uploaded.",
        )
    )
    serial = record.serial_number
    if serial:
        character_type = (
            "ASCII digits only"
            if re.fullmatch(r"[0-9]+", serial)
            else "ASCII alphanumeric"
            if re.fullmatch(r"[A-Za-z0-9]+", serial)
            else "Contains characters outside ASCII letters and digits"
        )
        checks.append(
            observation(
                "serial-observed",
                "Transmitted serial",
                "observed",
                f"{len(serial)} characters; {character_type}. Leading zeros and case are preserved.",
            )
        )
    evidence = batch.evidence if batch else {}
    minimum = positive_integer(evidence.get("Min SN Length"))
    maximum = positive_integer(evidence.get("Max SN Length"))
    if serial and minimum and maximum and minimum <= maximum:
        fits = minimum <= len(serial) <= maximum
        checks.append(
            observation(
                "serial-length",
                "Serial length against provided-batch reference",
                "consistent" if fits else "discrepancy",
                f"Transmitted length {len(serial)}; Snapshot range {minimum}–{maximum}. "
                + (
                    "Length is within the range; this does not confirm the serial exists or is authentic."
                    if fits
                    else "Length is outside the reference range. Check the transmitted value against the physical pack and the reference date."
                ),
            )
        )
    else:
        checks.append(
            observation(
                "serial-length",
                "Serial length against provided-batch reference",
                "unknown",
                "No usable length range for the exact provided batch is available. A different stored batch is not used as a substitute.",
            )
        )
    length = positive_integer(evidence.get("Batch Length"))
    if provided and length:
        checks.append(
            observation(
                "batch-length",
                "Batch length against Snapshot reference",
                "consistent" if len(provided) == length else "discrepancy",
                f"Transmitted length {len(provided)}; Snapshot reference {length}.",
            )
        )
    checks.append(
        observation(
            "format",
            "Batch / serial format",
            "unknown",
            "Source format codes are reference data only until their semantics are verified. No format or root-cause verdict is inferred.",
        )
    )
    return checks


def report_plan(record, checks, *, task=None, report=None, supported=True):
    """Bound a useful source request; IMT never enters this preparation action."""
    local = record.is_intermarket == 0 and record.source_market in {"CH", "LI"}
    if report:
        return {
            "action": "reuse",
            "reason": "Reuse the retained exact-pack report. Inspect its coverage before requesting an explicit refresh.",
        }
    if task and task.status in {"queued", "running"}:
        return {
            "action": "pending",
            "reason": "An exact-pack report is already queued or running; no duplicate request is needed.",
        }
    if not local:
        return {
            "action": "review",
            "reason": "Intermarket or unresolved market responsibility: NMVO review is needed before requesting further evidence.",
        }
    if not supported:
        return {
            "action": "review",
            "reason": "A supported product code scheme, product code or serial number is missing.",
        }
    if any(
        c["code"] == "serial-length" and c["result"] == "discrepancy" for c in checks
    ):
        return {
            "action": "compare",
            "reason": "Check the serial discrepancy with the physical pack first; a report for a possibly misread serial may add no information.",
        }
    if record.error_code == "A2":
        return {
            "action": "uploads",
            "reason": "Review product/batch upload evidence first. A pack report is not requested just because a batch is missing.",
        }
    if record.error_code in {"A3", "A7", "A24", "A52", "A68"}:
        return {
            "action": "request",
            "reason": "Pack history can clarify creation, prior handling or identifier discrepancies. Prepare one report for this exact pack; related exceptions reuse it.",
        }
    return {
        "action": "review",
        "reason": "No automatic report recommendation is defined for this alert type.",
    }


def collect(session, record):
    product = None
    if record.product_code_scheme and record.product_code:
        product = session.scalar(
            select(ProductSourceRecord).where(
                ProductSourceRecord.source_key
                == key(
                    record.source_namespace,
                    record.product_code_scheme,
                    record.product_code,
                ),
                ProductSourceRecord.source_namespace == record.source_namespace,
                ProductSourceRecord.is_observed == 1,
            )
        )
    publication = session.get(CurrentPublication, "product-batch")
    batches = {}
    if (
        product
        and publication
        and publication.source_namespace == record.source_namespace
    ):
        for role, code in [
            ("provided_batch", record.provided_batch),
            ("stored_batch", record.stored_batch),
        ]:
            if not code:
                continue
            batch = session.scalar(
                select(Batch).where(
                    Batch.batch_key == key(product.source_key, code),
                    Batch.product_source_id == product.id,
                    Batch.last_mapping_run_id == publication.mapping_run_id,
                    Batch.is_observed == 1,
                )
            )
            if batch and batch.batch_code == code:
                batches[role] = batch
    checks = identifier_checks(record, batches)
    task = report = None
    supported = True
    try:
        signature = record_signature(record)
    except ValueError:
        supported = False
    else:
        task = session.scalar(
            select(PackAuditRequest).where(
                PackAuditRequest.signature_key == signature,
                PackAuditRequest.source_namespace == record.source_namespace,
            )
        )
        if task and task.latest_report_id:
            candidate = session.get(PackAuditReport, task.latest_report_id)
            if (
                candidate
                and candidate.signature_key == signature
                and candidate.source_namespace == record.source_namespace
                and not candidate.is_example
            ):
                report = candidate
    repeat = repeat_evidence.repeat_sequence(session, record)
    checks.append(
        observation(
            "repeat",
            "Same-location repeated operation",
            "observed" if repeat else "unknown",
            "The retained audit evidence links an earlier successful change and rejected repeat at the same reported location. The reason still needs confirmation."
            if repeat
            else "No accepted same-location repeated-operation sequence is established for this exception.",
        )
    )
    return {
        "version": VERSION,
        "checks": checks,
        "batch_references": [
            batch_reference(
                batch,
                role="Provided batch" if role == "provided_batch" else "Stored batch",
            )
            for role, batch in batches.items()
        ],
        "snapshot_date": publication.snapshot_date.isoformat()
        if product
        and publication
        and publication.source_namespace == record.source_namespace
        else None,
        "repeat": repeat,
        "report_plan": report_plan(
            record, checks, task=task, report=report, supported=supported
        ),
        "report_id": report.id if report else None,
        "report_captured_at": report.captured_at if report else None,
        "report_source_as_of": report.source_data_as_of if report else None,
    }
