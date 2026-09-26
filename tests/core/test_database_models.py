from sqlalchemy.dialects import mysql

from app.core.db.models import Base


def test_integration_foundation_metadata_contains_only_approved_tables() -> None:
    assert set(Base.metadata.tables) == {
        "integration_jobs",
        "acquired_artifacts",
        "artifact_contents",
        "processing_runs",
        "staging_datasets",
        "staging_rows",
    }


def test_artifact_uses_longblob_and_staging_rows_do_not_store_raw_csv_lines() -> None:
    artifact = Base.metadata.tables["artifact_contents"]
    staging_row = Base.metadata.tables["staging_rows"]

    assert isinstance(artifact.c.artifact_bytes.type.dialect_impl(mysql.dialect()), mysql.LONGBLOB)
    assert "raw_csv_line" not in staging_row.c
