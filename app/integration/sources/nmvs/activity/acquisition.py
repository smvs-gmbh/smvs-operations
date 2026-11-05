import hashlib
from datetime import datetime, time

from app.core.db.models import AcquiredArtifact, IntegrationJob
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.sources.nmvs.activity.processing import process_activity


class UserActivityAcquisition:
    def __init__(self, client):
        self.client = client

    def run(self, session, start, end):
        require_idle_runtime_session(session)
        job = IntegrationJob(
            source_name="NMVS",
            channel_name="Reporting API",
            report_type="UserActivityReport",
            from_date=datetime.combine(start, time.min),
            to_date=datetime.combine(end, time(23, 59, 59)),
            status="acquiring",
            started_at=utcnow(),
            created_at=utcnow(),
            requested_api_version=self.client.api_version,
        )
        job_id = None
        try:
            session.add(job)
            session.flush()
            job_id = job.id
            session.commit()
            response = self.client.get_activity(start, end)
            content = MySQLArtifactStore._get_or_create_content(
                session, hashlib.sha256(response.content).hexdigest(), response.content
            )
            artifact = AcquiredArtifact(
                integration_job_id=job.id,
                content=content,
                source_name="NMVS",
                channel_name="Reporting API",
                report_type="UserActivityReport",
                source_uri=response.report_uri,
                content_type=response.content_type,
                report_metadata=response.report_metadata,
                received_at=utcnow(),
                processing_status="acquired",
                created_at=utcnow(),
            )
            session.add(artifact)
            session.flush()
            artifact_id = artifact.id
            job.status, job.used_api_version = (
                "artifact_acquired",
                response.used_api_version,
            )
            session.commit()
        except Exception as error:  # noqa: BLE001 - retain sanitized durable failure
            fail_execution(session, error, "activity_acquisition", job_id=job_id)
        process_activity(session, artifact_id, initial_job_id=job_id)
        return job
