from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db.models import (
    AcquiredArtifact,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.integration.artifacts.storage import utcnow
from app.integration.sources.nmvs.parsing import ParsedDailySnapshot, record_hash


def stage_daily_snapshot(
    session: Session,
    artifact: AcquiredArtifact,
    parsed: ParsedDailySnapshot,
    processing_run: ProcessingRun,
) -> ProcessingRun:
    if processing_run.id is None or processing_run.artifact_id != artifact.id:
        raise ValueError("Staging requires an existing processing run for this acquisition.")

    for dataset in parsed.datasets:
        staging_dataset = StagingDataset(
            processing_run_id=processing_run.id,
            artifact_id=artifact.id,
            source_dataset_name=dataset.source_dataset_name,
            section_order=dataset.section_order,
            source_headers=list(dataset.source_headers),
            row_count=len(dataset.rows),
            extraction_status="extracted",
            created_at=utcnow(),
        )
        session.add(staging_dataset)
        session.flush()
        for row_number, row in enumerate(dataset.rows, start=1):
            session.add(
                StagingRow(
                    staging_dataset_id=staging_dataset.id,
                    source_row_number=row_number,
                    source_record_hash=record_hash(row),
                    raw_row_json=row,
                    created_at=utcnow(),
                )
            )

    session.flush()
    return processing_run
