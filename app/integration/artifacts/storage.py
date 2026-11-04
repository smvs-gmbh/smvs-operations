from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db.models import AcquiredArtifact, ArtifactContent, IntegrationJob
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
        content = self._get_or_create_content(session, digest, response.content)

        artifact = AcquiredArtifact(
            integration_job_id=job.id,
            content=content,
            source_name="NMVS",
            channel_name="Reporting API",
            report_type="DailySnapshot",
            source_uri=response.report_uri,
            content_type=response.content_type,
            report_metadata={
                "report": response.report_metadata,
                "requested_api_version": response.requested_api_version,
                "used_api_version": response.used_api_version,
            },
            received_at=utcnow(),
            processing_status="acquired",
            created_at=utcnow(),
        )
        session.add(artifact)
        session.flush()
        return artifact

    def save_sai_export(self, session: Session, job: IntegrationJob, *, content_bytes: bytes,
                        source_uri: str, content_type: str | None,
                        metadata: dict[str, str]) -> AcquiredArtifact:
        digest = hashlib.sha256(content_bytes).hexdigest()
        content = self._get_or_create_content(session, digest, content_bytes)
        artifact = AcquiredArtifact(
            integration_job_id=job.id, content=content,
            source_name="Refdata SAI", channel_name="Public XML Export", report_type="SAIFullExport",
            source_uri=source_uri, content_type=content_type, report_metadata=metadata,
            received_at=utcnow(), processing_status="acquired", created_at=utcnow(),
        )
        session.add(artifact)
        session.flush()
        return artifact

    @staticmethod
    def _get_or_create_content(session: Session, digest: str, data: bytes) -> ArtifactContent:
        statement = select(ArtifactContent).where(ArtifactContent.sha256 == digest)
        content = session.scalar(statement)
        if content is None:
            try:
                # Isolate a concurrent checksum collision from the acquisition transaction.
                with session.begin_nested():
                    content = ArtifactContent(
                        sha256=digest, content_length=len(data), artifact_bytes=data, created_at=utcnow(),
                    )
                    session.add(content)
                    session.flush()
            except IntegrityError:
                # A locking read sees the winner even under MySQL REPEATABLE READ.
                content = session.scalar(statement.with_for_update())
                if content is None:
                    raise
        if content.content_length != len(data) or content.artifact_bytes != data:
            raise ValueError("Artifact checksum collision or stored content integrity failure.")
        return content
