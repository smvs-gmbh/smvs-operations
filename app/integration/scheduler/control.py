"""Persistent UI commands. Network work belongs to the scheduler, never a GET/POST handler."""

from datetime import UTC, date, datetime

from sqlalchemy import select

from app.core.db.models import ImportExecution, ImportMutex, ImportSchedule
from app.core.db.session import require_runtime_session
from app.domain.mapping import key
from app.domain.models import ManualImportRequest
from app.integration.artifacts.storage import utcnow

QUEUE_LOCK = "queue:imports-ui"
SOURCES = {
    "sai": {
        "name": "Refdata SAI",
        "rule": "Latest full export",
        "backfill": False,
        "time": "04:00",
        "note": "Imports the latest full export. Published product names change only after the separate publication step.",
    },
    "daily_snapshot": {
        "name": "Daily Snapshot",
        "rule": "Current UTC snapshot day",
        "backfill": True,
        "time": "04:15",
        "note": "Retrieves and stages the current snapshot, then publishes products, batches and participants using the selected SAI reference. Historical backfills remain staging-only.",
    },
    "user_activity": {
        "name": "User Activity",
        "rule": "Complete UTC days; fill gaps and refresh the latest 7 days",
        "backfill": True,
        "time": "05:00",
        "note": "Verification and IMT Fulfilment, excluding Synthetic Monitoring.",
    },
    "exceptions": {
        "name": "Exceptions API",
        "rule": "Through now; fill gaps and refresh the latest 7 days",
        "backfill": True,
        "time": "04:00",
        "note": "The current UTC day is partial. Existing Alerts are reused by source identity.",
    },
    "pack_uploads": {
        "name": "Pack Uploads",
        "rule": "Complete UTC days; fill gaps and refresh the latest 3 days",
        "backfill": True,
        "time": "05:15",
        "note": "Genuine transactions only. Upload evidence is scoped to product and batch, not an individual serial.",
    },
}


def validate_period(import_key, start, end, *, today=None):
    if import_key not in SOURCES or not SOURCES[import_key]["backfill"]:
        raise ValueError("Historical retrieval is not supported for this source.")
    today = today or datetime.now(UTC).date()
    if (
        not isinstance(start, date)
        or not isinstance(end, date)
        or end < start
        or (end - start).days > 30
    ):
        raise ValueError("Select 1 to 31 UTC days.")
    if import_key == "daily_snapshot" and start != end:
        raise ValueError("Select one snapshot date.")
    if end > today or import_key in ("user_activity", "pack_uploads") and end >= today:
        raise ValueError("This source requires completed UTC days.")


def enqueue(factory, import_key, *, kind="run_now", start=None, end=None):
    if import_key not in SOURCES or kind not in ("run_now", "backfill"):
        raise ValueError("Unknown import action.")
    if kind == "backfill":
        validate_period(import_key, start, end)
    elif start is not None or end is not None:
        raise ValueError("Run now uses the automatic period rule.")
    fingerprint = key(import_key, kind, str(start), str(end))
    with factory() as lock:
        require_runtime_session(lock)
        lock.execute(
            select(ImportMutex.import_key)
            .where(ImportMutex.import_key == QUEUE_LOCK)
            .with_for_update()
        ).scalar_one()
        with factory() as s:
            schedule = s.scalar(
                select(ImportSchedule).where(ImportSchedule.import_key == import_key)
            )
            if not schedule:
                raise ValueError("Configure this import first.")
            existing = s.scalar(
                select(ManualImportRequest).where(
                    ManualImportRequest.request_key == fingerprint,
                    ManualImportRequest.status.in_(("queued", "running")),
                )
            )
            if existing:
                s.expunge(existing)
                return existing
            if kind == "run_now" and s.scalar(
                select(ImportExecution.id)
                .where(
                    ImportExecution.schedule_id == schedule.id,
                    ImportExecution.status == "running",
                )
                .limit(1)
            ):
                return None
            task = ManualImportRequest(
                schedule_id=schedule.id,
                request_key=fingerprint,
                kind=kind,
                start_date=start,
                end_date=end,
                status="queued",
                attempt_count=0,
                requested_at=utcnow(),
            )
            s.add(task)
            s.commit()
            s.expunge(task)
            return task


def cancel(factory, request_id):
    with factory() as s:
        require_runtime_session(s)
        task = s.scalar(
            select(ManualImportRequest)
            .where(ManualImportRequest.id == request_id)
            .with_for_update()
        )
        if not task or task.status != "queued":
            raise ValueError("Only queued requests can be cancelled.")
        task.status, task.completed_at, task.retry_at = "cancelled", utcnow(), None
        s.commit()
