import hashlib
import json
from datetime import UTC

from app.core.db.models import AcquiredArtifact, IntegrationJob
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.sources.nmvs.exceptions.parsing import parse_page
from app.integration.sources.nmvs.exceptions.processing import process_exceptions


def save(session, job, content, *, report_type, uri, metadata):
    stored = MySQLArtifactStore._get_or_create_content(
        session, hashlib.sha256(content).hexdigest(), content
    )
    artifact = AcquiredArtifact(
        integration_job_id=job.id,
        content=stored,
        source_name="NMVS",
        channel_name="Exceptions API",
        report_type=report_type,
        source_uri=uri,
        content_type="application/json",
        report_metadata=metadata,
        received_at=utcnow(),
        created_at=utcnow(),
        processing_status="acquired",
    )
    session.add(artifact)
    session.flush()
    return artifact


class ExceptionsAcquisition:
    def __init__(self, client, authority):
        self.client, self.authority = client, authority

    def run(self, session, start, end):
        require_idle_runtime_session(session)
        job = IntegrationJob(
            source_name="NMVS",
            channel_name="Exceptions API",
            report_type="ExceptionsQuery",
            from_date=start.astimezone(UTC).replace(tzinfo=None, microsecond=0),
            to_date=end.astimezone(UTC).replace(tzinfo=None, microsecond=0),
            requested_api_version=self.client.api_version,
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
            request_id, parameters = self.client.request(start, end)
            page_ids = []
            for phase in ("initial", "full"):
                page_ids = []
                page = 1
                total_pages = 1
                while page <= total_pages:
                    response = self.client.page(request_id, page)
                    uri = self.client._base_url + "/alerts/data/" + request_id
                    artifact = save(
                        session,
                        job,
                        response.content,
                        report_type="ExceptionsQueryPage",
                        uri=uri,
                        metadata={
                            "request_id": request_id,
                            "page": page,
                            "phase": phase,
                            "filter": parameters,
                            "used_api_version": response.headers.get(
                                "emvs-api-version"
                            ),
                        },
                    )
                    artifact_id = artifact.id
                    session.commit()  # Retain every successful source response before validation.
                    data = response.json()
                    if data.get("isOverLimit", False):
                        raise ValueError(
                            "Exception result exceeds source limit; use a smaller query period."
                        )
                    if (
                        data.get("isTruncated") is True
                        and phase == "initial"
                        and page == 1
                    ):
                        request_id = self.client.escalate(request_id)
                        break
                    checked = parse_page(response.content, page)
                    total_pages = max(1, checked["pages"])
                    page_ids.append(artifact_id)
                    page += 1
                else:
                    break
            manifest = {
                "page_artifact_ids": page_ids,
                "request_id": request_id,
                "filter": parameters,
            }
            artifact = save(
                session,
                job,
                json.dumps(manifest, separators=(",", ":")).encode(),
                report_type="ExceptionsQuery",
                uri=self.client._base_url + "/alerts/data/" + request_id,
                metadata={
                    "generated_manifest": True,
                    "authority": self.authority,
                    **manifest,
                },
            )
            artifact_id = artifact.id
            job.status = "artifact_acquired"
            job.used_api_version = response.headers.get("emvs-api-version")
            session.commit()
        except Exception as error:  # noqa: BLE001 - preserve sanitized acquisition failures
            fail_execution(session, error, "exceptions_acquisition", job_id=job_id)
        run = process_exceptions(session, artifact_id, initial_job_id=job_id)
        return job, run
