import hashlib
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

from sqlalchemy import or_, select

from app.core.db.models import AcquiredArtifact, ImportMutex, IntegrationJob
from app.core.db.session import require_runtime_session
from app.domain.mapping import canonical, key, source_rows
from app.domain.models import NMVSException, PackAuditReport, PackAuditRequest
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow
from app.integration.sources.nmvs.connection import reporting_client
from app.integration.sources.nmvs.pack_audit.api import PackAuditClient
from app.integration.sources.nmvs.pack_audit.parsing import parse_pack_audit, scheme
from app.integration.sources.nmvs.pack_audit.processing import (
    PARSER_VERSION,
    process_pack_audit,
)

QUEUE_LOCK = "queue:pack-audit"
WORKER_LOCK = "worker:pack-audit"


def signature(namespace, code_scheme, code, serial):
    # Source spelling is part of the retrieval signature; no serial repair or fuzzy correlation.
    if not scheme(code_scheme) or not all(
        isinstance(v, str) and 0 < len(v) <= 100 for v in (code, serial)
    ):
        raise ValueError(
            "Product code scheme, product code and serial number are required."
        )
    return key(namespace, code_scheme, code, serial)


def record_signature(record):
    return signature(
        record.source_namespace,
        record.product_code_scheme,
        record.product_code,
        record.serial_number,
    )


def request_report(factory, exception_id, *, refresh=False):
    with factory() as lock:
        require_runtime_session(lock)
        lock.execute(
            select(ImportMutex.import_key)
            .where(ImportMutex.import_key == QUEUE_LOCK)
            .with_for_update()
        ).scalar_one()
        with factory() as s:
            record = s.get(NMVSException, exception_id)
            if not record:
                raise ValueError("Exception not found.")
            sig = record_signature(record)
            task = s.scalar(
                select(PackAuditRequest).where(PackAuditRequest.signature_key == sig)
            )
            if task and (
                task.status in ("queued", "running")
                or task.latest_report_id
                and not refresh
            ):
                s.expunge(task)
                return task
            now = utcnow()
            if not task:
                task = PackAuditRequest(
                    signature_key=sig,
                    source_namespace=record.source_namespace,
                    code_scheme=record.product_code_scheme,
                    product_code=record.product_code,
                    serial_number=record.serial_number,
                    created_at=now,
                )
                s.add(task)
            task.request_title = "SMVS Operations Pack " + uuid.uuid4().hex
            task.requested_for_exception_id = record.id
            task.status, task.attempt_count, task.requested_at = "queued", 0, now
            task.last_error, task.completed_at, task.retry_at = None, None, None
            s.commit()
            s.expunge(task)
            return task


def retain(session, content, uri, metadata, *, example=False):
    now = utcnow()
    job = IntegrationJob(
        source_name="NMVS",
        channel_name="Provided example" if example else "Reporting API",
        report_type="PackAuditTrailReport",
        status="acquiring",
        requested_api_version=metadata.get("requested_api_version"),
        used_api_version=metadata.get("used_api_version"),
        started_at=now,
        created_at=now,
    )
    session.add(job)
    session.flush()
    stored = MySQLArtifactStore._get_or_create_content(
        session, hashlib.sha256(content).hexdigest(), content
    )
    artifact = AcquiredArtifact(
        integration_job_id=job.id,
        content=stored,
        source_name="NMVS",
        channel_name=job.channel_name,
        report_type="PackAuditTrailReport",
        source_uri=uri,
        content_type="text/csv",
        report_metadata=metadata,
        received_at=now,
        created_at=now,
        processing_status="acquired",
    )
    session.add(artifact)
    session.flush()
    aid, jid = artifact.id, job.id
    session.commit()
    run = process_pack_audit(session, aid, initial_job_id=jid)
    return run.id


def publish(session, run_id, namespace, parameters, *, example=False):
    require_runtime_session(session)
    run, artifact = canonical(session, run_id, "NMVS", "PackAuditTrailReport")
    if run.parser_version != PARSER_VERSION:
        raise ValueError("Unexpected pack parser version.")
    if not example:
        uri = urlsplit(artifact.source_uri or "")
        if namespace != f"nmvs-origin:{uri.scheme}://{uri.netloc}":
            raise ValueError("Pack source authority mismatch.")
    elif artifact.channel_name != "Provided example":
        raise ValueError("Invalid example evidence.")
    if artifact.report_metadata.get("request") != parameters:
        raise ValueError("Pack parameters mismatch.")
    sig = signature(
        namespace,
        parameters["productCodeScheme"],
        parameters["productCode"],
        parameters["serialNumber"],
    )
    version = key(sig, artifact.content_id, PARSER_VERSION)
    existing = session.scalar(
        select(PackAuditReport).where(PackAuditReport.version_key == version)
    )
    if existing:
        return existing
    events = [raw for _, raw in source_rows(session, run.id, "PackAuditTrail")]
    report = PackAuditReport(
        version_key=version,
        signature_key=sig,
        source_namespace=namespace,
        code_scheme=parameters["productCodeScheme"],
        product_code=parameters["productCode"],
        serial_number=parameters["serialNumber"],
        processing_run_id=run.id,
        acquired_artifact_id=artifact.id,
        captured_at=artifact.received_at,
        source_data_as_of=artifact.report_metadata.get("data_available_at_request"),
        is_example=int(example),
        metadata_json=run.file_metadata or {},
        events_json=events,
    )
    session.add(report)
    session.flush()
    return report


def tick(factory):
    """One serial queued retrieval. Durable state plus source-request correlation permits recovery."""
    with factory() as lock:
        require_runtime_session(lock)
        owned = lock.scalar(
            select(ImportMutex)
            .where(ImportMutex.import_key == WORKER_LOCK)
            .with_for_update(skip_locked=True)
        )
        if owned is None:
            return None
        with factory() as s:
            task = s.scalar(
                select(PackAuditRequest)
                .where(
                    PackAuditRequest.status.in_(("queued", "running")),
                    or_(
                        PackAuditRequest.retry_at.is_(None),
                        PackAuditRequest.retry_at <= utcnow(),
                    ),
                )
                .order_by(PackAuditRequest.requested_at)
                .limit(1)
            )
            if not task:
                return None
            task.status = "running"
            task.attempt_count += 1
            s.commit()
            identifier = task.id
            parameters = {
                "productCodeScheme": task.code_scheme,
                "productCode": task.product_code,
                "serialNumber": task.serial_number,
            }
            namespace, title, requested = (
                task.source_namespace,
                task.request_title,
                task.requested_at,
            )
        client = None
        try:
            client = reporting_client(PackAuditClient)
            response = client.get_pack(parameters, title=title, created_at=requested)
            with factory() as s:
                run_id = retain(
                    s,
                    response.content,
                    response.report_uri,
                    {
                        **response.report_metadata,
                        "requested_api_version": getattr(
                            response, "requested_api_version", None
                        ),
                        "used_api_version": getattr(response, "used_api_version", None),
                    },
                )
                report = publish(s, run_id, namespace, parameters)
                task = s.get(PackAuditRequest, identifier)
                task.latest_report_id, task.status, task.completed_at = (
                    report.id,
                    "ready",
                    utcnow(),
                )
                task.last_error, task.retry_at = None, None
                s.commit()
        except Exception:  # noqa: BLE001 - keep source and credentials out of diagnostics
            with factory() as s:
                task = s.get(PackAuditRequest, identifier)
                task.status = "queued" if task.attempt_count < 3 else "failed"
                task.retry_at = (
                    utcnow() + timedelta(minutes=5) if task.status == "queued" else None
                )
                task.last_error = "The report could not be retrieved or unambiguously matched to the pack."
                task.completed_at = utcnow()
                s.commit()
        finally:
            if client:
                client.close()
        return identifier


def import_example(factory, path):
    content = path.read_bytes()
    parsed = parse_pack_audit(content)
    metadata = parsed.file_metadata
    params = {
        "productCodeScheme": metadata["Product Code Scheme"],
        "productCode": metadata["Product Code"],
        "serialNumber": metadata["Pack Serial Number"],
    }
    with factory() as lock:
        require_runtime_session(lock)
        lock.execute(
            select(ImportMutex.import_key)
            .where(ImportMutex.import_key == WORKER_LOCK)
            .with_for_update()
        ).scalar_one()
        with factory() as s:
            run_id = retain(
                s,
                content,
                None,
                {"request": params, "provided_example": True},
                example=True,
            )
            report = publish(
                s, run_id, "provided-example:pack-audit", params, example=True
            )
            s.commit()
            return report.id
