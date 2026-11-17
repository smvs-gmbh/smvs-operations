from app.core.db.models import AcquiredArtifact, IntegrationJob, ProcessingRun
from app.integration.artifacts.storage import utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.idempotency import reusable_result
from app.integration.sources.nmvs.uploads.parsing import instant, parse_upload
from app.integration.staging.service import stage_daily_snapshot

PARSER_VERSION = "product-pack-upload-1"
REPORT_TYPE = "ProductPackUploadAuditTrailReport"


def process_upload(session, artifact_id, *, initial_job_id=None):
    require_idle_runtime_session(session)
    run_id = None
    try:
        artifact = session.get(AcquiredArtifact, artifact_id)
        if (
            not artifact
            or artifact.source_name != "NMVS"
            or artifact.report_type != REPORT_TYPE
        ):
            raise ValueError("Expected upload artifact.")
        run = ProcessingRun(
            artifact_id=artifact.id,
            run_type="initial_extraction" if initial_job_id else "replay",
            parser_version=PARSER_VERSION,
            transform_version="none",
            status="extracting",
            started_at=utcnow(),
        )
        session.add(run)
        session.flush()
        run_id = run.id
        session.commit()
        parsed = parse_upload(artifact.artifact_bytes)
        params = artifact.report_metadata.get("request", {})
        for k, field in (
            ("startDateTime", "Start Date & Time (UTC)"),
            ("endDateTime", "End Date & Time (UTC)"),
        ):
            if instant(params[k]) != instant(parsed.file_metadata[field]):
                raise ValueError("Downloaded upload period mismatch.")
        title = artifact.report_metadata.get("report", {}).get("title")
        if title and parsed.file_metadata.get("Report Name") != title:
            raise ValueError("Downloaded upload request mismatch.")
        run.file_metadata = parsed.file_metadata
        previous = reusable_result(session, artifact, run)
        if previous:
            run.reused_from_run_id = previous.id
        else:
            stage_daily_snapshot(session, artifact, parsed, run)
        run.status, run.completed_at, artifact.processing_status = (
            "succeeded",
            utcnow(),
            "staged",
        )
        if initial_job_id:
            job = session.get(IntegrationJob, initial_job_id)
            job.status, job.completed_at = "succeeded", utcnow()
        session.commit()
        return run
    except Exception as error:  # noqa: BLE001
        fail_execution(
            session,
            error,
            "upload_extraction",
            artifact_id=artifact_id,
            processing_run_id=run_id,
            job_id=initial_job_id,
        )
