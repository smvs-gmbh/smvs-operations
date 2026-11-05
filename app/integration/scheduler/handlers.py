from app.core.db.session import SessionFactory
from app.integration.sources.nmvs.daily_snapshot import DailySnapshotAcquisition
from app.integration.sources.sai.acquisition import SAIAcquisition
from app.integration.sources.sai.client import SAIClient


def import_sai():
    client = SAIClient()
    try:
        with SessionFactory() as session:
            return SAIAcquisition(client).run(session)
    finally:
        client.close()


def import_daily_snapshot():
    from app.integration.sources.nmvs.connection import reporting_client

    client = reporting_client()
    try:
        with SessionFactory() as session:
            return DailySnapshotAcquisition(client).run(session)
    finally:
        client.close()


def import_user_activity():
    from app.domain.activity.service import scheduled_import

    return scheduled_import(SessionFactory)


def import_exceptions():
    from app.domain.exceptions.service import scheduled_import

    return scheduled_import(SessionFactory)


def import_pack_uploads():
    from app.domain.uploads.service import scheduled_import

    return scheduled_import(SessionFactory)


def default_handlers():
    # Register additional source runners here; the scheduler remains independent
    # of source protocols, credentials and parsing logic.
    return {
        "sai": import_sai,
        "daily_snapshot": import_daily_snapshot,
        "user_activity": import_user_activity,
        "exceptions": import_exceptions,
        "pack_uploads": import_pack_uploads,
    }


def import_backfill(key, start, end):
    """One explicit historical window, independent of the automatic cadence."""
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.core.db.models import AcquiredArtifact, IntegrationJob

    if key == "daily_snapshot":
        from app.integration.sources.nmvs.connection import reporting_client

        client = reporting_client()
        try:
            with SessionFactory() as s:
                return DailySnapshotAcquisition(client).run(s, today=start)
        finally:
            client.close()
    if key == "user_activity":
        from app.domain.activity.service import import_period
        from app.integration.sources.nmvs.activity.api import UserActivityClient
        from app.integration.sources.nmvs.connection import reporting_client

        client = reporting_client(UserActivityClient)
        try:
            job_id, _ = import_period(SessionFactory, client, start, end)
        finally:
            client.close()
    elif key == "exceptions":
        from app.domain.exceptions.service import import_days

        job_id = import_days(SessionFactory, start, end)
    elif key == "pack_uploads":
        from datetime import datetime, timedelta

        from app.domain.models import UploadReport, UploadRequest
        from app.domain.uploads.service import request_report, tick

        task = request_report(
            SessionFactory,
            get_settings().nmvs_exceptions_authority,
            datetime.combine(start, datetime.min.time()),
            datetime.combine(end + timedelta(days=1), datetime.min.time()),
        )
        if task.status != "ready":
            tick(SessionFactory, task_id=task.id)
        with SessionFactory() as s:
            task = s.get(UploadRequest, task.id)
            if task.status != "ready":
                raise ValueError(
                    "Upload report is not ready; the request is retained for retry."
                )
            report = s.get(UploadReport, task.latest_report_id)
            job_id = s.scalar(
                select(AcquiredArtifact.integration_job_id).where(
                    AcquiredArtifact.id == report.acquired_artifact_id
                )
            )
    else:
        raise ValueError("Historical retrieval is not supported.")
    with SessionFactory() as s:
        job = s.get(IntegrationJob, job_id)
        s.expunge(job)
        return job
