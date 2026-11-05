from app.core.db.models import AcquiredArtifact, IntegrationJob, ProcessingRun
from app.integration.artifacts.storage import utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.idempotency import reusable_result
from app.integration.sources.nmvs.activity.parsing import parse_activity
from app.integration.staging.service import stage_daily_snapshot

PARSER_VERSION = "user-activity-1"


def process_activity(session, artifact_id, *, initial_job_id=None):
    require_idle_runtime_session(session)
    run_id = None
    try:
        artifact = session.get(AcquiredArtifact, artifact_id)
        if not artifact or (
            artifact.source_name,
            artifact.channel_name,
            artifact.report_type,
        ) != (
            "NMVS",
            "Reporting API",
            "UserActivityReport",
        ):
            raise ValueError("Expected NMVS User Activity acquisition.")
        if initial_job_id is not None and artifact.integration_job_id != initial_job_id:
            raise ValueError("Acquisition job mismatch.")
        run = ProcessingRun(
            artifact_id=artifact_id,
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
        parsed = parse_activity(artifact.artifact_bytes)
        expected = artifact.report_metadata.get("request", {})
        if expected and (expected.get("startDate"), expected.get("endDate")) != (
            parsed.start.isoformat(),
            parsed.end.isoformat(),
        ):
            raise ValueError("Activity workbook dates differ from acquisition request.")
        report = artifact.report_metadata.get("report", {})
        if report.get("title") and report["title"] != parsed.metadata.get(
            "Report Name"
        ):
            raise ValueError(
                "Activity workbook identity differs from acquisition request."
            )
        run.file_metadata = parsed.metadata
        session.commit()
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
    except Exception as error:  # noqa: BLE001 - retain sanitized durable failure
        fail_execution(
            session,
            error,
            "activity_extraction",
            artifact_id=artifact_id,
            processing_run_id=run_id,
            job_id=initial_job_id,
        )
