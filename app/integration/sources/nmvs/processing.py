from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db.models import AcquiredArtifact, IntegrationJob, ProcessingRun
from app.integration.artifacts.storage import utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.sources.nmvs.parsing import (
    parse_daily_snapshot,
    validate_csv_content_type,
)
from app.integration.staging.service import stage_daily_snapshot

PARSER_VERSION = "daily-snapshot-parser-2"


def replay_daily_snapshot(session: Session, artifact_id: int, *, parser_version: str = PARSER_VERSION) -> ProcessingRun:
    """Process retained acquisition bytes; no source client or acquisition call."""
    return process_daily_snapshot(session, artifact_id, parser_version=parser_version)


def process_daily_snapshot(session: Session, artifact_id: int, *, parser_version: str = PARSER_VERSION,
                           initial_job_id: int | None = None) -> ProcessingRun:
    require_idle_runtime_session(session)
    run_id = None
    stage = "processing_start"
    try:
        artifact = session.get(AcquiredArtifact, artifact_id)
        if artifact is None:
            raise ValueError("Acquisition does not exist.")
        if (artifact.source_name, artifact.channel_name, artifact.report_type) != ("NMVS", "Reporting API", "DailySnapshot"):
            raise ValueError("Acquisition is not an NMVS Daily Snapshot.")
        if initial_job_id is not None and artifact.integration_job_id != initial_job_id:
            raise ValueError("Acquisition does not belong to the initial job.")
        run = ProcessingRun(
            artifact_id=artifact_id,
            run_type="initial_extraction" if initial_job_id is not None else "replay",
            parser_version=parser_version,
            transform_version="none",
            status="extracting",
            started_at=utcnow(),
        )
        session.add(run)
        session.flush()
        run_id = run.id
        session.commit()  # Durable attempt before any parsing or staging work.

        stage = "extraction"
        validate_csv_content_type(artifact.content_type)
        parsed = parse_daily_snapshot(artifact.artifact_bytes)
        run.status = "staging"
        session.commit()

        stage = "staging"
        stage_daily_snapshot(session, artifact, parsed, processing_run=run)
        run.status = "succeeded"
        run.completed_at = utcnow()
        artifact.processing_status = "staged"
        if initial_job_id is not None:
            job = session.get(IntegrationJob, initial_job_id)
            job.status = "succeeded"
            job.completed_at = utcnow()
        # Staging rows and all success markers commit together.
        session.commit()
        return run
    except Exception as error:  # noqa: BLE001 - isolate and sanitize every processing failure
        fail_execution(session, error, stage, job_id=initial_job_id,
                       artifact_id=artifact_id, processing_run_id=run_id)
