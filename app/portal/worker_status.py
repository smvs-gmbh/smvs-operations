"""Read-only worker liveness and evidence-request progress, without source calls."""

from datetime import timedelta

from sqlalchemy import select

from app.core.db.models import ImportExecution
from app.domain.models import PackAuditRequest, SchedulerHeartbeat, UploadRequest
from app.integration.artifacts.storage import utcnow

HEARTBEAT_MAX_AGE = timedelta(seconds=60)
QUEUE_PICKUP_DELAY = timedelta(minutes=2)


def worker_state(session, *, now=None):
    now = now or utcnow()
    heartbeats = session.scalars(
        select(SchedulerHeartbeat)
        .order_by(SchedulerHeartbeat.last_seen_at.desc())
        .limit(20)
    ).all()
    live = [h for h in heartbeats if h.status in {"running", "manual"}
            and now - HEARTBEAT_MAX_AGE <= h.last_seen_at <= now + timedelta(seconds=15)]
    return {
        "workers": live,
        "automatic_workers": [h for h in live if h.status == "running"],
        "last_heartbeat": heartbeats[0] if heartbeats else None,
        "available": bool(live),
        "started_at": live[0].started_at if live else None,
        "last_seen_at": (live[0] if live else heartbeats[0]).last_seen_at
        if heartbeats else None,
    }


def pack_audit_progress(session, task, worker, *, now=None):
    now = now or utcnow()
    if not task or task.status not in {"queued", "running"}:
        return None
    if not worker["available"]:
        return {
            "title": "Waiting for background worker" if task.status == "queued"
            else "Processing status not confirmed",
            "message": "No recent worker heartbeat. The request is retained; processing cannot currently be confirmed.",
        }
    if task.status == "running":
        return {"title": "Retrieving report …",
                "message": "The worker has picked up this request. Retrieval and processing are in progress."}
    if task.retry_at and task.retry_at > now:
        return {"title": "Retry scheduled",
                "message": f"Next attempt no earlier than {task.retry_at:%Y-%m-%d %H:%M:%S} UTC."}
    active_import = session.scalar(
        select(ImportExecution.id).where(
            ImportExecution.status == "running", ImportExecution.completed_at.is_(None)
        ).limit(1)
    )
    other_report = any(session.scalar(select(model.id).where(model.status == "running").limit(1))
                       for model in (PackAuditRequest, UploadRequest))
    if active_import or other_report:
        return {"title": "Queued behind background work",
                "message": "Another import or report is marked as running. This request remains in the queue."}
    eligible_since = max(task.requested_at, task.retry_at or task.requested_at,
                         worker["started_at"] or task.requested_at)
    if now - eligible_since > QUEUE_PICKUP_DELAY:
        return {"title": "Queue pickup delayed",
                "message": "The worker has a recent heartbeat, but has not picked up this request within two minutes. Check background-worker status or contact the administrator."}
    return {"title": "Queued · worker available",
            "message": "A worker has a recent heartbeat. This request is waiting to be picked up."}
