from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.db.models import ImportExecution, ImportSchedule, IntegrationJob
from app.domain.models import (
    ActivityDay,
    CurrentPublication,
    ExceptionPublication,
    ManualImportAttempt,
    ManualImportRequest,
    PackAuditRequest,
    SchedulerHeartbeat,
    UploadReport,
    UploadRequest,
)
from app.integration.artifacts.storage import utcnow
from app.integration.scheduler.control import SOURCES
from app.portal.exception_queries import namespace

REPORT_TYPES = {
    "sai": "SAIFullExport",
    "daily_snapshot": "DailySnapshot",
    "user_activity": "UserActivityReport",
    "exceptions": "ExceptionsQuery",
    "pack_uploads": "ProductPackUploadAuditTrailReport",
}


def window_coverage(windows, now):
    if not windows:
        return "No accepted history yet"
    first, last = min(a for a, b in windows), max(b for a, b in windows)
    end = min(
        last.replace(hour=0, minute=0, second=0, microsecond=0),
        now.replace(hour=0, minute=0, second=0, microsecond=0),
    )
    start = first.replace(hour=0, minute=0, second=0, microsecond=0)
    expected = max(0, (end - start).days)
    merged = []
    for a, b in sorted(windows):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    complete = 0
    for a, b in merged:
        midnight = a.replace(hour=0, minute=0, second=0, microsecond=0)
        whole_start = midnight + timedelta(days=1) if a > midnight else midnight
        whole_end = min(end, b.replace(hour=0, minute=0, second=0, microsecond=0))
        complete += max(0, (whole_end - whole_start).days)
    return f"{first:%Y-%m-%d} → {last:%Y-%m-%d %H:%M} UTC · {complete}/{expected} complete UTC days"


def overview(session, *, source=""):
    now, ns = utcnow(), namespace(session)
    schedules = {s.import_key: s for s in session.scalars(select(ImportSchedule))}
    heartbeats = session.scalars(
        select(SchedulerHeartbeat)
        .order_by(SchedulerHeartbeat.last_seen_at.desc())
        .limit(20)
    ).all()
    live = [
        h
        for h in heartbeats
        if h.status == "running" and h.last_seen_at >= now - timedelta(seconds=60)
    ]
    current = session.get(CurrentPublication, "product-batch")
    coverage = {
        "sai": f"Published export: {current.sai_exported_at:%Y-%m-%d}"
        if current
        else "No published SAI context",
        "daily_snapshot": f"Published snapshot: {current.snapshot_date:%Y-%m-%d}"
        if current
        else "No published Snapshot context",
    }
    activity = session.execute(
        select(ActivityDay.activity_date, ActivityDay.section).where(
            ActivityDay.source_namespace == ns
        )
    ).all()
    if activity:
        first, last = min(d for d, _ in activity), max(d for d, _ in activity)
        coverage["user_activity"] = (
            f"{first} → {last} · {len(activity)}/{((last - first).days + 1) * 2} section-days"
        )
    else:
        coverage["user_activity"] = "No accepted history yet"
    exceptions = session.execute(
        select(
            ExceptionPublication.period_start, ExceptionPublication.period_end
        ).where(ExceptionPublication.source_namespace == ns)
    ).all()
    coverage["exceptions"] = window_coverage(
        [(a, b + timedelta(milliseconds=1)) for a, b in exceptions], now
    )
    uploads = session.execute(
        select(UploadReport.period_start, UploadReport.period_end).where(
            UploadReport.source_namespace == ns
        )
    ).all()
    coverage["pack_uploads"] = window_coverage(uploads, now)
    successful_imports = dict(
        session.execute(
            select(ImportExecution.schedule_id, func.max(ImportExecution.completed_at))
            .where(ImportExecution.status == "succeeded")
            .group_by(ImportExecution.schedule_id)
        ).all()
    )
    cards = []
    for key, meta in SOURCES.items():
        schedule = schedules.get(key)
        executions = (
            session.scalars(
                select(ImportExecution)
                .where(ImportExecution.schedule_id == schedule.id)
                .order_by(ImportExecution.id.desc())
                .limit(1)
            ).all()
            if schedule
            else []
        )
        busy = bool(
            schedule
            and session.scalar(
                select(ImportExecution.id)
                .where(
                    ImportExecution.schedule_id == schedule.id,
                    ImportExecution.status == "running",
                )
                .limit(1)
            )
        )
        queued = bool(
            schedule
            and session.scalar(
                select(ManualImportRequest.id)
                .where(
                    ManualImportRequest.schedule_id == schedule.id,
                    ManualImportRequest.kind == "run_now",
                    ManualImportRequest.status.in_(("queued", "running")),
                )
                .limit(1)
            )
        )
        last_job = session.scalar(
            select(IntegrationJob)
            .where(IntegrationJob.report_type == REPORT_TYPES[key])
            .order_by(IntegrationJob.id.desc())
            .limit(1)
        )
        success = session.scalar(
            select(IntegrationJob)
            .where(
                IntegrationJob.report_type == REPORT_TYPES[key],
                IntegrationJob.status == "succeeded",
            )
            .order_by(IntegrationJob.id.desc())
            .limit(1)
        )
        cards.append(
            {
                **meta,
                "key": key,
                "schedule": schedule,
                "busy": busy,
                "queued": queued,
                "last_execution": executions[0] if executions else None,
                "last_successful_import": successful_imports.get(schedule.id)
                if schedule
                else None,
                "last_job": last_job,
                "last_success": success,
                "coverage": coverage[key],
                "next_local": schedule.next_run_at.replace(tzinfo=UTC).astimezone(
                    ZoneInfo(schedule.timezone)
                )
                if schedule and schedule.enabled
                else None,
            }
        )
    history_query = (
        select(ImportExecution, ImportSchedule.import_key, ManualImportRequest)
        .join(ImportSchedule, ImportExecution.schedule_id == ImportSchedule.id)
        .outerjoin(
            ManualImportAttempt, ManualImportAttempt.execution_id == ImportExecution.id
        )
        .outerjoin(
            ManualImportRequest,
            ManualImportRequest.id == ManualImportAttempt.request_id,
        )
    )
    request_query = select(ManualImportRequest, ImportSchedule.import_key).join(
        ImportSchedule, ManualImportRequest.schedule_id == ImportSchedule.id
    )
    if source:
        history_query = history_query.where(ImportSchedule.import_key == source)
        request_query = request_query.where(ImportSchedule.import_key == source)
    history = session.execute(
        history_query.order_by(ImportExecution.id.desc()).limit(30)
    ).all()
    requests = session.execute(
        request_query.order_by(ManualImportRequest.id.desc()).limit(20)
    ).all()
    evidence_pending = []
    for model, label in [
        (PackAuditRequest, "Pack Audit Trail"),
        (UploadRequest, "Upload reports"),
    ]:
        tasks = session.scalars(
            select(model).where(
                model.source_namespace == ns, model.status.in_(("queued", "running"))
            )
        ).all()
        evidence_pending.append((label, len(tasks)))
    return {
        "cards": cards,
        "workers": live,
        "last_heartbeat": heartbeats[0] if heartbeats else None,
        "history": history,
        "requests": requests,
        "source_filter": source,
        "sources": SOURCES,
        "evidence_pending": evidence_pending,
        "today": datetime.now(UTC).date(),
        "yesterday": datetime.now(UTC).date() - timedelta(days=1),
    }
