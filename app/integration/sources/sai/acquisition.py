from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db.models import IntegrationJob
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.sources.sai.client import PAGE_URL, SAIClient
from app.integration.sources.sai.processing import process_sai


class SAIAcquisition:
    def __init__(
        self, client: SAIClient, artifact_store: MySQLArtifactStore | None = None
    ):
        self.client = client
        self.artifact_store = artifact_store or MySQLArtifactStore()

    def run(self, session: Session) -> IntegrationJob:
        require_idle_runtime_session(session)
        job = IntegrationJob(
            source_name="Refdata SAI",
            channel_name="Public XML Export",
            report_type="SAIFullExport",
            status="acquiring",
            started_at=utcnow(),
            created_at=utcnow(),
        )
        job_id = None
        stage = "acquisition_start"
        try:
            session.add(job)
            session.flush()
            job_id = job.id
            session.commit()
            stage = "discovery"
            export = self.client.discover()
            stage = "acquisition"
            content, content_type = self.client.download(export)
            artifact = self.artifact_store.save_sai_export(
                session,
                job,
                content_bytes=content,
                source_uri=export.url,
                content_type=content_type,
                metadata={
                    "listing_url": PAGE_URL,
                    "filename": export.filename,
                    "exported_at_source": export.exported_at.isoformat(),
                    "exported_at_timezone": "unspecified",
                    "delivery_mode": "full",
                },
            )
            artifact_id = artifact.id
            job.requested_snapshot_date = export.exported_at.date()
            job.status = "artifact_acquired"
            session.commit()
        except Exception as error:  # noqa: BLE001 - sanitize before crossing the integration boundary
            fail_execution(session, error, stage, job_id=job_id)
        process_sai(session, artifact_id, initial_job_id=job_id)
        return job
