"""Generate report fixtures for the isolated Alert Desk workspace."""

import csv
import io
from datetime import timedelta

from sqlalchemy import select

from app.core.db.models import ProcessingRun
from app.domain.mapping import key, source_rows
from app.domain.models import NMVSException, PackAuditReport, PackAuditRequest
from app.domain.pack_audit.service import record_signature, retain
from app.integration.sources.nmvs.pack_audit.parsing import HEADERS


def report_csv(alert):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        (
            "Report Type",
            "Report Name",
            "Product Code Scheme",
            "Product Code",
            "Pack Serial Number",
        )
    )
    writer.writerow(
        (
            "Pack Audit Trail Report",
            "Synthetic demo report",
            alert.product_code_scheme,
            alert.product_code,
            alert.serial_number,
        )
    )
    writer.writerow(())
    writer.writerow(HEADERS)

    def add(at, suffix, name, message, fields, code=""):
        writer.writerow(
            (
                at.isoformat(timespec="milliseconds") + "Z",
                "Synthetic demo",
                f"{alert.unique_alert_id}-{suffix}",
                code,
                name,
                message,
                alert.provided_batch,
                message,
                " ".join(
                    f"{field}: {value};" for field, value in fields.items() if value
                ),
                "PROCESS",
                "ERROR" if code else "INFO",
            )
        )

    at = alert.alert_at
    location = {"Market": alert.source_market, "Location": alert.source_location_id}
    operation = alert.evidence["attemptedOperation"]
    scenario = {
        "A2": ("PackVerificationFailedBatchNotFound", "Batch not found"),
        "A3": ("PackVerificationFailedPackNotFound", "Pack not found"),
        "A7": (
            "IntermarketFailedAlreadyInRequestedState",
            "Pack already in the requested state",
        ),
        "A24": (
            "PackStateChangeRejected",
            "Pack previously supplied at a different location",
        ),
    }
    if alert.error_code in ("A7", "A24"):
        state = "Exported" if alert.error_code == "A7" else "Supplied"
        add(
            at - timedelta(days=7),
            "create",
            "PpdNewPackCreated",
            "Synthetic pack created",
            {"AttemptedOperation": "CREATED", "Market": "EU"},
        )
        previous_location = (
            {**location, "Location": alert.last_update_location_id}
            if alert.error_code == "A24"
            else location
        )
        add(
            at - timedelta(minutes=10),
            "change",
            "PackStateChanged",
            "Synthetic state change",
            {
                **previous_location,
                "InitialState": "Active",
                "ActualState": state,
                "TargetState": state,
                "AttemptedOperation": operation,
            },
        )
        location |= {"InitialState": state, "ActualState": state, "TargetState": state}

    name, message = scenario[alert.error_code]
    add(
        at,
        "alert",
        name,
        message,
        {**location, "AttemptedOperation": operation, "AlertId": alert.unique_alert_id},
        alert.error_code,
    )
    return output.getvalue().encode()


def seed_pack_audits(factory, namespace, codes):
    with factory() as session:
        alerts = session.scalars(
            select(NMVSException).where(
                NMVSException.source_namespace == namespace,
                NMVSException.error_code.in_(codes),
                NMVSException.alert_at.is_not(None),
            )
        ).all()
        for alert in alerts:
            signature = record_signature(alert)
            task = session.scalar(
                select(PackAuditRequest).where(
                    PackAuditRequest.signature_key == signature
                )
            )
            if task and task.latest_report_id:
                continue
            parameters = {
                "productCodeScheme": alert.product_code_scheme,
                "productCode": alert.product_code,
                "serialNumber": alert.serial_number,
            }
            run_id = retain(
                session, report_csv(alert), None, {"request": parameters}, example=True
            )
            run = session.get(ProcessingRun, run_id)
            if run.reused_from_run_id is not None:
                run = session.get(ProcessingRun, run.reused_from_run_id)
            report = PackAuditReport(
                version_key=key(signature, "synthetic-demo-v1"),
                signature_key=signature,
                source_namespace=namespace,
                code_scheme=alert.product_code_scheme,
                product_code=alert.product_code,
                serial_number=alert.serial_number,
                processing_run_id=run.id,
                acquired_artifact_id=run.artifact_id,
                captured_at=alert.alert_at,
                is_example=0,
                metadata_json=run.file_metadata,
                events_json=[
                    raw for _, raw in source_rows(session, run.id, "PackAuditTrail")
                ],
            )
            session.add(report)
            session.flush()
            if task is None:
                task = PackAuditRequest(
                    signature_key=signature,
                    source_namespace=namespace,
                    code_scheme=alert.product_code_scheme,
                    product_code=alert.product_code,
                    serial_number=alert.serial_number,
                    created_at=alert.alert_at,
                )
                session.add(task)
            task.request_title = "Synthetic demo report"
            task.requested_for_exception_id = alert.id
            task.status = "ready"
            task.attempt_count = 0
            task.requested_at = task.completed_at = alert.alert_at
            task.latest_report_id = report.id
            task.last_error = task.retry_at = None
            session.commit()
