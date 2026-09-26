import importlib.util
import io
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0003_file_metadata.py"
    spec = importlib.util.spec_from_file_location("file_metadata_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_runs_remain_null_and_downgrade_preserves_rows():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE processing_runs (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO processing_runs VALUES (1)")
        revision = migration()
        revision.op = Operations(MigrationContext.configure(connection))
        revision.upgrade()
        column = sa.inspect(connection).get_columns("processing_runs")[1]
        assert column["name"] == "file_metadata" and column["nullable"]
        assert isinstance(column["type"], sa.JSON)
        assert connection.exec_driver_sql("SELECT id, file_metadata FROM processing_runs").all() == [(1, None)]
        revision.downgrade()
        assert connection.exec_driver_sql("SELECT * FROM processing_runs").all() == [(1,)]
        assert [c["name"] for c in sa.inspect(connection).get_columns("processing_runs")] == ["id"]
    engine.dispose()


@pytest.mark.parametrize("direction,expected", [
    ("upgrade", "ALTER TABLE processing_runs ADD COLUMN file_metadata JSON;"),
    ("downgrade", "ALTER TABLE processing_runs DROP COLUMN file_metadata;"),
])
def test_mysql_ddl_without_connection(direction, expected):
    revision = migration()
    assert revision.revision == "0003_file_metadata"
    assert revision.down_revision == "0002_artifact_content_and_failure_stage"
    output = io.StringIO()
    revision.op = Operations(MigrationContext.configure(
        dialect_name="mysql", opts={"as_sql": True, "output_buffer": output},
    ))
    getattr(revision, direction)()
    assert output.getvalue().strip() == expected
