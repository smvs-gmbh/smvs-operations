from datetime import UTC, date, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.db.models import (
    AcquiredArtifact,
    ArtifactContent,
    Base,
    IntegrationJob,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.integration.sources.nmvs.parsing import ExtractedDataset, ParsedDailySnapshot
from app.integration.staging.service import stage_daily_snapshot


def test_stages_dynamic_datasets_and_empty_dataset_without_raw_csv_lines() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        job = IntegrationJob(
            source_name="NMVS",
            channel_name="Reporting API",
            report_type="DailySnapshot",
            requested_snapshot_date=date(2026, 9, 25),
            status="artifact_acquired",
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(job)
        session.flush()
        artifact = AcquiredArtifact(
            integration_job_id=job.id,
            source_name="NMVS",
            channel_name="Reporting API",
            report_type="DailySnapshot",
            content=ArtifactContent(
                content_length=3,
                sha256="a" * 64,
                artifact_bytes=b"csv",
                created_at=datetime.now(UTC).replace(tzinfo=None),
            ),
            report_metadata={"Report Type": "DailySnapshot"},
            received_at=datetime.now(UTC).replace(tzinfo=None),
            processing_status="acquired",
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(artifact)
        session.flush()
        parsed = ParsedDailySnapshot(
            file_metadata={"Report Type": "DailySnapshot"},
            datasets=(
                ExtractedDataset("Products", 1, ("Product Code",), ({"Product Code": "001"},)),
                ExtractedDataset("Empty Dataset", 2, ("A", "B"), ()),
            ),
        )

        run = ProcessingRun(
            artifact_id=artifact.id, run_type="initial_extraction", parser_version="1",
            transform_version="none", status="staging", started_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(run)
        session.flush()
        stage_daily_snapshot(session, artifact, parsed, processing_run=run)
        session.commit()

        datasets = session.scalars(select(StagingDataset).order_by(StagingDataset.section_order)).all()
        rows = session.scalars(select(StagingRow)).all()

        assert run.status == "staging"  # Completion belongs to the transaction orchestrator.
        assert [(dataset.source_dataset_name, dataset.row_count) for dataset in datasets] == [
            ("Products", 1),
            ("Empty Dataset", 0),
        ]
        assert len(rows) == 1
        assert rows[0].source_row_number == 1
        assert rows[0].raw_row_json == {"Product Code": "001"}
        assert "raw_csv_line" not in StagingRow.__table__.c
