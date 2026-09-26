import hashlib
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.ext.compiler import compiles, deregister

from app.core.db.models import Base

VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def load_migration(name):
    spec = importlib.util.spec_from_file_location(name, VERSIONS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def migration_database():
    # Execute migration operations only on an in-memory SQLite double. Its batch
    # table rebuilds differ from MySQL ALTER TABLE; this is not a MySQL DDL test.
    @compiles(LONGBLOB, "sqlite")
    def blob_double(element, compiler, **kwargs):
        return "BLOB"

    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            old = load_migration("0001_integration_foundation")
            old.op = Operations(context)
            old.upgrade()
            connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('0001_integration_foundation')")
            new = load_migration("0002_artifact_content_and_failure_stage")
            new.op = Operations(context)
            yield connection, new
    finally:
        engine.dispose()
        deregister(LONGBLOB)


def table(connection, name):
    return sa.Table(name, sa.MetaData(), autoload_with=connection)


def seed(connection, corrupt=False):
    now = datetime(2026, 9, 25, tzinfo=UTC).replace(tzinfo=None)
    connection.execute(table(connection, "integration_jobs").insert(), {
        "id": 41, "source_name": "NMVS", "channel_name": "Reporting API",
        "report_type": "DailySnapshot", "status": "succeeded", "created_at": now,
    })
    data = b"original report bytes\r\n"
    connection.execute(table(connection, "acquired_artifacts").insert(), {
        "id": 73, "integration_job_id": 41, "source_name": "NMVS", "channel_name": "Reporting API",
        "report_type": "DailySnapshot", "source_uri": "/reports/73", "content_type": "text/csv",
        "content_length": len(data), "sha256": "0" * 64 if corrupt else hashlib.sha256(data).hexdigest(),
        "report_metadata": {"source": "original", "used_api_version": "1"}, "received_at": now,
        "processing_status": "staged", "artifact_bytes": data, "created_at": now,
    })
    connection.execute(table(connection, "processing_runs").insert(), {
        "id": 101, "artifact_id": 73, "run_type": "initial_extraction", "parser_version": "1",
        "transform_version": "none", "status": "succeeded", "started_at": now,
    })
    connection.execute(table(connection, "staging_datasets").insert(), {
        "id": 202, "processing_run_id": 101, "artifact_id": 73, "source_dataset_name": "Products",
        "section_order": 1, "source_headers": ["Code"], "row_count": 1,
        "extraction_status": "extracted", "created_at": now,
    })
    connection.execute(table(connection, "staging_rows").insert(), {
        "id": 303, "staging_dataset_id": 202, "source_row_number": 1,
        "source_record_hash": "b" * 64, "raw_row_json": {"Code": "001"}, "created_at": now,
    })


def snapshot(connection, names):
    return {name: [dict(row) for row in connection.execute(sa.select(table(connection, name))).mappings()]
            for name in names}


@pytest.mark.parametrize("populated", [False, True])
def test_upgrade_matches_models_and_preserves_all_ids_and_provenance(migration_database, populated):
    connection, migration = migration_database
    if populated:
        seed(connection)
    names = ["integration_jobs", "acquired_artifacts", "processing_runs", "staging_datasets", "staging_rows"]
    before = snapshot(connection, names)
    migration.upgrade()
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    version_column = sa.inspect(connection).get_columns("alembic_version")[0]
    assert version_column["type"].length >= len(migration.revision)
    after = snapshot(connection, names)
    for name in names:
        if name not in {"integration_jobs", "acquired_artifacts"}:
            assert before[name] == after[name]
    if populated:
        old = before["acquired_artifacts"][0]
        new = after["acquired_artifacts"][0]
        content = snapshot(connection, ["artifact_contents"])["artifact_contents"][0]
        assert new["id"] == 73 and new["content_id"] == content["id"]
        moved = {"sha256", "content_length", "artifact_bytes"}
        assert {k: new[k] for k in old if k not in moved} == {k: v for k, v in old.items() if k not in moved}
        assert all(content[k] == old[k] for k in moved)
        assert after["integration_jobs"][0] == {**before["integration_jobs"][0], "failure_stage": None}
    assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    migration.downgrade()
    assert snapshot(connection, names) == before


def test_corrupt_legacy_content_refuses_before_ddl(migration_database):
    connection, migration = migration_database
    seed(connection, corrupt=True)
    with pytest.raises(RuntimeError, match="integrity check failed"):
        migration.upgrade()
    assert "artifact_contents" not in sa.inspect(connection).get_table_names()
    assert "failure_stage" not in table(connection, "integration_jobs").c


@pytest.mark.parametrize("kind", ["duplicate_acquisition", "failure_stage", "orphan_content"])
def test_downgrade_refuses_provenance_loss_before_ddl(migration_database, kind):
    connection, migration = migration_database
    seed(connection)
    migration.upgrade()
    if kind == "duplicate_acquisition":
        artifacts = table(connection, "acquired_artifacts")
        original = dict(connection.execute(sa.select(artifacts)).mappings().one())
        connection.execute(artifacts.insert(), {**original, "id": 74})
    elif kind == "failure_stage":
        connection.execute(table(connection, "integration_jobs").update().values(failure_stage="extraction"))
    else:
        connection.execute(table(connection, "artifact_contents").insert(), {
            "id": 99, "sha256": hashlib.sha256(b"orphan").hexdigest(), "content_length": 6,
            "artifact_bytes": b"orphan", "created_at": datetime(2026, 9, 25, tzinfo=UTC).replace(tzinfo=None),
        })
    with pytest.raises(RuntimeError, match="refused before schema changes"):
        migration.downgrade()
    assert "artifact_contents" in sa.inspect(connection).get_table_names()
    assert "artifact_bytes" not in table(connection, "acquired_artifacts").c


def test_backfill_verifier_prevents_dropping_original_bytes(migration_database, monkeypatch):
    connection, migration = migration_database
    seed(connection)
    original_verify = migration._validate_backfill

    def corrupt_then_verify(connection, artifacts, contents):
        connection.execute(contents.update().values(artifact_bytes=b"bad copy"))
        original_verify(connection, artifacts, contents)

    monkeypatch.setattr(migration, "_validate_backfill", corrupt_then_verify)
    with pytest.raises(RuntimeError, match="backfill verification failed"):
        migration.upgrade()
    assert "artifact_bytes" in table(connection, "acquired_artifacts").c
    with pytest.raises(RuntimeError, match="inspect migration state"):
        migration.upgrade()
