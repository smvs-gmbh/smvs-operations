from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db.models import AcquiredArtifact, IntegrationJob
from app.integration.sources.nmvs.reporting import DailySnapshotResponse


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class MySQLArtifactStore:
    def save_daily_snapshot(
        self,
        session: Session,
        job: IntegrationJob,
        response: DailySnapshotResponse,
    ) -> AcquiredArtifact:
        digest = hashlib.sha256(response.content).hexdigest()
        existing = session.scalar(
            select(AcquiredArtifact).where(AcquiredArtifact.sha256 == digest)
        )
        if existing is not None:
            return existing

        artifact = AcquiredArtifact(
            integration_job_id=job.id,
            source_name="NMVS",
            channel_name="Reporting API",
            report_type="DailySnapshot",
            source_uri=response.report_uri,
            content_type=response.content_type,
            content_length=len(response.content),
            sha256=digest,
            report_metadata={
                "report": response.report_metadata,
                "requested_api_version": response.requested_api_version,
                "used_api_version": response.used_api_version,
            },
            received_at=utcnow(),
            processing_status="acquired",
            artifact_bytes=response.content,
            created_at=utcnow(),
        )
        session.add(artifact)
        session.flush()
        return artifact
