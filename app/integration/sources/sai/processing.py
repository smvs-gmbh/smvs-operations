from __future__ import annotations

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.db.models import (
    AcquiredArtifact,
    IntegrationJob,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.integration.artifacts.storage import utcnow
from app.integration.failures import fail_execution, require_idle_runtime_session
from app.integration.idempotency import reusable_result
from app.integration.sources.nmvs.parsing import record_hash
from app.integration.sources.sai.parsing import parse_sai

PARSER_VERSION = "sai-xml-3.2-parser-1"


def process_sai(
    session: Session, artifact_id: int, *, initial_job_id: int | None = None
) -> ProcessingRun:
    require_idle_runtime_session(session)
    run_id, stage = None, "processing_start"
    try:
        artifact = session.get(AcquiredArtifact, artifact_id)
        if artifact is None or (
            artifact.source_name,
            artifact.channel_name,
            artifact.report_type,
        ) != ("Refdata SAI", "Public XML Export", "SAIFullExport"):
            raise ValueError("Acquisition is not a SAI full export.")
        if initial_job_id is not None and artifact.integration_job_id != initial_job_id:
            raise ValueError("Acquisition does not belong to the initial job.")
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
        stage = "extraction"
        parsed = parse_sai(artifact.artifact_bytes)
        run.file_metadata = parsed.file_metadata
        run.status = "staging"
        session.commit()
        stage = "staging"
        previous = reusable_result(session, artifact, run)
        if previous is not None:
            run.reused_from_run_id = previous.id
        else:
            for dataset in parsed.datasets:
                target = StagingDataset(
                    processing_run_id=run.id,
                    artifact_id=artifact.id,
                    source_dataset_name=dataset.source_dataset_name,
                    section_order=dataset.section_order,
                    source_headers=list(dataset.source_headers),
                    row_count=len(dataset.rows),
                    extraction_status="extracted",
                    created_at=utcnow(),
                )
                session.add(target)
                session.flush()
                for offset in range(0, len(dataset.rows), 1000):
                    session.execute(
                        insert(StagingRow),
                        [
                            {
                                "staging_dataset_id": target.id,
                                "source_row_number": offset + number,
                                "source_record_hash": record_hash(row),
                                "raw_row_json": row,
                                "created_at": utcnow(),
                            }
                            for number, row in enumerate(
                                dataset.rows[offset : offset + 1000], 1
                            )
                        ],
                    )
        run.status, run.completed_at = "succeeded", utcnow()
        artifact.processing_status = "staged"
        if initial_job_id is not None:
            job = session.get(IntegrationJob, initial_job_id)
            job.status, job.completed_at = "succeeded", utcnow()
        session.commit()
        return run
    except Exception as error:  # noqa: BLE001 - durable, sanitized integration failures
        fail_execution(
            session,
            error,
            stage,
            job_id=initial_job_id,
            artifact_id=artifact_id,
            processing_run_id=run_id,
        )


def replay_sai(session: Session, artifact_id: int) -> ProcessingRun:
    """Re-extract retained bytes without contacting Refdata."""
    return process_sai(session, artifact_id)
