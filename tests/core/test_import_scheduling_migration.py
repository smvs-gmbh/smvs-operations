import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

from app.core.db.models import Base
from app.domain.models import DOMAIN_TABLES


def test_additive_migration_preserves_existing_processing_and_rows_and_downgrades():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/0004_import_scheduling.py"
    )
    spec = importlib.util.spec_from_file_location("scheduling_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    before = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        if not table.name.startswith("import_") and table.name not in DOMAIN_TABLES:
            table.to_metadata(before)
    runs = before.tables["processing_runs"]
    for constraint in list(runs.foreign_key_constraints):
        if constraint.name == "fk_processing_runs_reused_from":
            runs.constraints.remove(constraint)
    runs._columns.remove(runs.c.reused_from_run_id)
    before.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO processing_runs (id,artifact_id,run_type,parser_version,transform_version,status,started_at) VALUES (1,1,'initial_extraction','test','none','succeeded','2026-11-04')"
        )
        connection.exec_driver_sql(
            "INSERT INTO staging_datasets (id,processing_run_id,artifact_id,source_dataset_name,section_order,source_headers,row_count,extraction_status,created_at) VALUES (1,1,1,'test',1,'[]',0,'extracted','2026-11-04')"
        )
        context = MigrationContext.configure(connection)
        migration.op = Operations(context)
        migration.upgrade()
        expected = sa.MetaData()
        for table in Base.metadata.sorted_tables:
            if table.name not in DOMAIN_TABLES:
                table.to_metadata(expected)
        assert compare_metadata(context, expected) == []
        assert connection.exec_driver_sql(
            "SELECT id,reused_from_run_id FROM processing_runs"
        ).all() == [(1, None)]
        assert connection.exec_driver_sql("SELECT id FROM staging_datasets").all() == [
            (1,)
        ]
        migration.downgrade()
        assert compare_metadata(context, before) == []
        assert connection.exec_driver_sql("SELECT id FROM staging_datasets").all() == [
            (1,)
        ]
    engine.dispose()
