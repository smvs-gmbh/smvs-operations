from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.db.models import IntegrationJob
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow
from app.integration.sources.nmvs.parsing import parse_daily_snapshot
from app.integration.sources.nmvs.reporting import ReportingApiClient
from app.integration.staging.service import stage_daily_snapshot


class DailySnapshotAcquisition:
    def __init__(self, client: ReportingApiClient, artifact_store: MySQLArtifactStore | None = None) -> None:
        self._client = client
        self._artifact_store = artifact_store or MySQLArtifactStore()

    def run(self, session: Session, days_in_past: int = 0, today: date | None = None) -> IntegrationJob:
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
            status="created",
            created_at=utcnow(),
        )
        session.add(job)
        session.commit()

        job.status = "acquiring"
        job.started_at = utcnow()
        session.commit()
        try:
            response = self._client.get_daily_snapshot(requested_date, requested_date)
            job.used_api_version = response.used_api_version
            artifact = self._artifact_store.save_daily_snapshot(session, job, response)
            job.status = "artifact_acquired"
            session.commit()
        except Exception as exc:
            self._mark_failed(session, job, "acquisition", exc)
            raise

        try:
            parsed = parse_daily_snapshot(artifact.artifact_bytes)
            stage_daily_snapshot(session, artifact, parsed)
            session.commit()
            job.status = "succeeded"
            job.completed_at = utcnow()
            session.commit()
            return job
        except Exception as exc:
            session.rollback()
            self._mark_failed(session, job, "extraction_or_staging", exc)
            raise

    @staticmethod
    def _mark_failed(session: Session, job: IntegrationJob, stage: str, error: Exception) -> None:
        session.rollback()
        job.status = "failed"
        job.completed_at = utcnow()
        job.failure_code = error.__class__.__name__
        job.failure_message = str(error)
        session.add(job)
        session.commit()
