from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.db.models import IntegrationJob
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.sources.nmvs.processing import process_daily_snapshot
from app.integration.sources.nmvs.reporting import ReportingApiClient


class DailySnapshotAcquisition:
    def __init__(self, client: ReportingApiClient, artifact_store: MySQLArtifactStore | None = None) -> None:
        self._client = client
        self._artifact_store = artifact_store or MySQLArtifactStore()

    def run(self, session: Session, days_in_past: int = 0, today: date | None = None) -> IntegrationJob:
        require_idle_runtime_session(session)
        requested_date = (today or datetime.now(UTC).date()) - timedelta(days=days_in_past)
        job = IntegrationJob(
            source_name="NMVS",
            channel_name="Reporting API",
            report_type="DailySnapshot",
            requested_snapshot_date=requested_date,
            days_in_past=days_in_past,
            from_date=requested_date,
            to_date=requested_date,
            requested_api_version=self._client.api_version,
            status="acquiring",
            started_at=utcnow(),
            created_at=utcnow(),
        )
        job_id = None
        try:
            session.add(job)
            session.flush()
            job_id = job.id
            session.commit()
        except Exception as error:  # noqa: BLE001 - sanitize failures before a job is durable
            fail_execution(session, error, "acquisition_start", job_id=job_id)
        try:
            response = self._client.get_daily_snapshot(requested_date, requested_date)
            job.used_api_version = response.used_api_version
            artifact = self._artifact_store.save_daily_snapshot(session, job, response)
            artifact_id = artifact.id
            job.status = "artifact_acquired"
            session.commit()
        except Exception as error:  # noqa: BLE001 - preserve safe acquisition error information
            fail_execution(session, error, "acquisition", job_id=job_id)

        process_daily_snapshot(session, artifact_id, initial_job_id=job_id)
        return job
