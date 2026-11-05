from app.core.db.models import AcquiredArtifact, IntegrationJob, ProcessingRun
from app.integration.artifacts.storage import utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.idempotency import reusable_result
from app.integration.sources.nmvs.pack_audit.parsing import parse_pack_audit, same_pack
from app.integration.staging.service import stage_daily_snapshot

PARSER_VERSION = "pack-audit-1"


def process_pack_audit(session, artifact_id, *, initial_job_id=None):
    require_idle_runtime_session(session)
    run_id = None
    try:
        artifact = session.get(AcquiredArtifact, artifact_id)
        if (
            not artifact
            or artifact.source_name != "NMVS"
            or artifact.report_type != "PackAuditTrailReport"
        ):
            raise ValueError("Expected a Pack Audit Trail artifact.")
        if artifact.channel_name not in ("Reporting API", "Provided example") or (
            initial_job_id is not None and artifact.integration_job_id != initial_job_id
        ):
            raise ValueError("Pack audit acquisition mismatch.")
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
        parsed = parse_pack_audit(artifact.artifact_bytes)
        if not same_pack(parsed.file_metadata, artifact.report_metadata["request"]):
            raise ValueError("Downloaded report belongs to another pack.")
        expected = artifact.report_metadata.get("report", {}).get("title")
        if expected and parsed.file_metadata.get("Report Name") != expected:
            raise ValueError("Downloaded report belongs to another request.")
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
    except Exception as error:  # noqa: BLE001 - retain sanitized source and database failures
        fail_execution(
            session,
            error,
            "pack_audit_extraction",
            artifact_id=artifact_id,
            processing_run_id=run_id,
            job_id=initial_job_id,
        )
