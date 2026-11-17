"""Reusable time-window evidence, explicitly queued; no source calls during portal reads."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import or_, select

from app.core.db.models import AcquiredArtifact, ImportMutex, IntegrationJob
from app.core.db.session import require_runtime_session
from app.domain.activity.service import source_namespace
from app.domain.mapping import canonical, key, source_rows
from app.domain.models import UploadReport, UploadRequest
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow
from app.integration.sources.nmvs.connection import reporting_client
from app.integration.sources.nmvs.uploads.api import UploadClient
from app.integration.sources.nmvs.uploads.parsing import instant, parse_upload
from app.integration.sources.nmvs.uploads.processing import (
    PARSER_VERSION,
    REPORT_TYPE,
    process_upload,
)

QUEUE_LOCK = "queue:uploads"
WORKER_LOCK = "worker:uploads"


def lock_row(session, name, *, skip=False):
    require_runtime_session(session)
    return session.scalar(
        select(ImportMutex)
        .where(ImportMutex.import_key == name)
        .with_for_update(skip_locked=skip)
    )


def request_report(factory, namespace, start, end, *, refresh=False):
    if (
        start.tzinfo
        or end.tzinfo
        or start >= end
        or end - start > timedelta(days=31)
        or end > utcnow()
    ):
        raise ValueError("Request at most 31 elapsed UTC days.")
    request_key = key(namespace, start.isoformat(), end.isoformat(), "genuine")
    with factory() as lock:
        if lock_row(lock, QUEUE_LOCK) is None:
            raise ValueError("Upload queue unavailable.")
        with factory() as s:
            task = s.scalar(
                select(UploadRequest).where(UploadRequest.request_key == request_key)
            )
            if task and (
                task.status in ("queued", "running")
                or task.latest_report_id
                and not refresh
            ):
                s.expunge(task)
                return task
            if not task:
                task = UploadRequest(
                    request_key=request_key,
                    source_namespace=namespace,
                    period_start=start,
                    period_end=end,
                )
                s.add(task)
            task.request_title = "SMVS Operations Upload " + uuid.uuid4().hex
            task.status, task.attempt_count, task.requested_at = "queued", 0, utcnow()
            task.completed_at, task.retry_at, task.last_error = None, None, None
            s.commit()
            s.expunge(task)
            return task


def retain(session, content, uri, metadata, *, provided=False):
    now = utcnow()
    job = IntegrationJob(
        source_name="NMVS",
        channel_name="Provided export" if provided else "Reporting API",
        report_type=REPORT_TYPE,
        requested_api_version=metadata.get("requested_api_version"),
        used_api_version=metadata.get("used_api_version"),
        status="acquiring",
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
        report_type=REPORT_TYPE,
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
    return process_upload(session, aid, initial_job_id=jid).id


def publish(session, run_id, namespace):
    require_runtime_session(session)
    run, artifact = canonical(session, run_id, "NMVS", REPORT_TYPE)
    if run.parser_version != PARSER_VERSION:
        raise ValueError("Unexpected upload parser.")
    if artifact.channel_name == "Reporting API":
        uri = urlsplit(artifact.source_uri or "")
        if namespace != f"nmvs-origin:{uri.scheme}://{uri.netloc}":
            raise ValueError("Upload source authority mismatch.")
    elif (
        artifact.channel_name != "Provided export"
        or artifact.report_metadata.get("source_namespace") != namespace
    ):
        raise ValueError("Upload provenance mismatch.")
    version = key(namespace, artifact.content_id, PARSER_VERSION)
    existing = session.scalar(
        select(UploadReport).where(UploadReport.version_key == version)
    )
    if existing:
        return existing
    meta = run.file_metadata
    report = UploadReport(
        version_key=version,
        source_namespace=namespace,
        period_start=instant(meta["Start Date & Time (UTC)"]),
        period_end=instant(meta["End Date & Time (UTC)"]),
        acquired_artifact_id=artifact.id,
        processing_run_id=run.id,
        captured_at=artifact.received_at,
        metadata_json=meta,
        events_json=[
            raw for _, raw in source_rows(session, run.id, "ProductPackUpload")
        ],
    )
    session.add(report)
    session.flush()
    return report


def tick(factory, *, task_id=None):
    with factory() as lock:
        if lock_row(lock, WORKER_LOCK, skip=True) is None:
            return None
        with factory() as s:
            query = select(UploadRequest).where(
                UploadRequest.status.in_(("queued", "running")),
                or_(
                    UploadRequest.retry_at.is_(None), UploadRequest.retry_at <= utcnow()
                ),
            )
            if task_id is not None:
                query = query.where(UploadRequest.id == task_id)
            task = s.scalar(query.order_by(UploadRequest.requested_at).limit(1))
            if not task:
                return None
            task.status, task.attempt_count = "running", task.attempt_count + 1
            s.commit()
            identifier, namespace = task.id, task.source_namespace
            start, end, title, requested = (
                task.period_start,
                task.period_end,
                task.request_title,
                task.requested_at,
            )
        client = None
        try:
            client = reporting_client(UploadClient, api_version="3.6")
            if source_namespace(client) != namespace:
                raise ValueError("Configured upload authority differs.")
            response = client.get_upload(start, end, title=title, created_at=requested)
            with factory() as s:
                run_id = retain(
                    s,
                    response.content,
                    response.report_uri,
                    {
                        **response.report_metadata,
                        "requested_api_version": response.requested_api_version,
                        "used_api_version": response.used_api_version,
                    },
                )
                report = publish(s, run_id, namespace)
                task = s.get(UploadRequest, identifier)
                task.latest_report_id, task.status, task.completed_at = (
                    report.id,
                    "ready",
                    utcnow(),
                )
                task.retry_at, task.last_error = None, None
                s.commit()
        except Exception:  # noqa: BLE001 - never expose source credentials or SQL parameters
            with factory() as s:
                task = s.get(UploadRequest, identifier)
                task.status = "queued" if task.attempt_count < 3 else "failed"
                task.retry_at = (
                    utcnow() + timedelta(minutes=5) if task.status == "queued" else None
                )
                task.completed_at = utcnow()
                task.last_error = "Upload report unavailable, or the period / Genuine Transactions filter could not be confirmed."
                s.commit()
        finally:
            if client:
                client.close()
        return identifier


def import_file(factory, path, namespace):
    content = path.read_bytes()
    meta = parse_upload(content).file_metadata
    with factory() as lock:
        if lock_row(lock, WORKER_LOCK) is None:
            raise ValueError("Upload worker unavailable.")
        with factory() as s:
            run_id = retain(
                s,
                content,
                None,
                {
                    "source_namespace": namespace,
                    "request": {
                        "startDateTime": meta["Start Date & Time (UTC)"],
                        "endDateTime": meta["End Date & Time (UTC)"],
                        "syntheticMonitoring": False,
                    },
                },
                provided=True,
            )
            report = publish(s, run_id, namespace)
            s.commit()
            return report.id


def covered(reports, start, end):
    cursor = start
    for report in sorted(reports, key=lambda r: r.period_start):
        if report.period_end <= cursor:
            continue
        if report.period_start > cursor:
            return False
        cursor = max(cursor, report.period_end)
        if cursor >= end:
            return True
    return False


def scheduled_import(factory):
    client = reporting_client(UploadClient, api_version="3.6")
    namespace = source_namespace(client)
    client.close()
    today = datetime.combine(datetime.now(UTC).date(), datetime.min.time())
    with factory() as s:
        reports = s.scalars(
            select(UploadReport).where(UploadReport.source_namespace == namespace)
        ).all()
    start = min(
        (r.period_start for r in reports), default=today - timedelta(days=1)
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    day, needed = start, []
    while day < today:
        if day >= today - timedelta(days=3) or not covered(
            reports, day, day + timedelta(days=1)
        ):
            needed.append(day)
        day += timedelta(days=1)
    # Coalesce adjacent missing days into source windows of at most 31 days.
    periods = []
    for day in needed:
        if (
            periods
            and periods[-1][1] == day
            and day + timedelta(days=1) - periods[-1][0] <= timedelta(days=31)
        ):
            periods[-1] = (periods[-1][0], day + timedelta(days=1))
        else:
            periods.append((day, day + timedelta(days=1)))
    last_job = None
    for start, end in periods:
        task = request_report(factory, namespace, start, end, refresh=True)
        tick(factory, task_id=task.id)
        with factory() as s:
            task = s.get(UploadRequest, task.id)
            if task.status != "ready":
                raise ValueError(
                    "Upload retrieval incomplete; queue retained for retry."
                )
            report = s.get(UploadReport, task.latest_report_id)
            artifact = s.get(AcquiredArtifact, report.acquired_artifact_id)
            last_job = s.get(IntegrationJob, artifact.integration_job_id)
            s.expunge(last_job)
    if last_job is None:
        raise ValueError("No complete UTC upload day available.")
    return last_job
