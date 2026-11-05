import json

from app.core.db.models import AcquiredArtifact, IntegrationJob, ProcessingRun
from app.integration.artifacts.storage import utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.idempotency import reusable_result
from app.integration.sources.nmvs.exceptions.parsing import parse_pages
from app.integration.sources.nmvs.parsing import ExtractedDataset, ParsedDailySnapshot
from app.integration.staging.service import stage_daily_snapshot

PARSER_VERSION = "exceptions-1"


def process_exceptions(session, artifact_id, *, initial_job_id=None):
    require_idle_runtime_session(session)
    run_id = None
    try:
        artifact = session.get(AcquiredArtifact, artifact_id)
        if not artifact or (
            artifact.source_name,
            artifact.channel_name,
            artifact.report_type,
        ) != ("NMVS", "Exceptions API", "ExceptionsQuery"):
            raise ValueError("Expected an Exceptions query manifest.")
        if initial_job_id is not None and artifact.integration_job_id != initial_job_id:
            raise ValueError("Exception acquisition job mismatch.")
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
        manifest = json.loads(artifact.artifact_bytes)
        ids = manifest["page_artifact_ids"]
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 1000
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Invalid exception page manifest.")
        contents = []
        for i, page_id in enumerate(ids, 1):
            page = session.get(AcquiredArtifact, page_id)
            if (
                page is None
                or page.integration_job_id != artifact.integration_job_id
                or page.report_type != "ExceptionsQueryPage"
                or page.source_name != "NMVS"
                or page.channel_name != "Exceptions API"
                or page.report_metadata.get("request_id") != manifest["request_id"]
                or page.report_metadata.get("page") != i
                or page.report_metadata.get("filter") != manifest["filter"]
            ):
                raise ValueError("Exception page does not belong to this query.")
            contents.append(page.artifact_bytes)
        rows = parse_pages(contents)
        previous = reusable_result(session, artifact, run)
        if previous:
            run.reused_from_run_id = previous.id
        else:
            headers = tuple(dict.fromkeys(k for row in rows for k in row))
            parsed = ParsedDailySnapshot(
                file_metadata={},
                datasets=(ExtractedDataset("Alerts", 1, headers, tuple(rows)),),
            )
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
    except Exception as error:  # noqa: BLE001 - sanitize source and driver diagnostics
        fail_execution(
            session,
            error,
            "exceptions_extraction",
            artifact_id=artifact_id,
            processing_run_id=run_id,
            job_id=initial_job_id,
        )
