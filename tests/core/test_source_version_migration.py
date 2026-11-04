import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext


def test_numeric_backfill_and_unresolved_downgrade_refusal_before_ddl():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/0006_source_version_values_retain_unresolved_source_version_values.py"
    )
    spec = importlib.util.spec_from_file_location("source_versions_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE product_source_records (id INTEGER PRIMARY KEY, reported_version INTEGER NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE product_versions (id INTEGER PRIMARY KEY, version_number INTEGER NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO product_source_records VALUES (1, 3)")
        connection.exec_driver_sql("INSERT INTO product_versions VALUES (1, 3)")
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert (
            connection.exec_driver_sql(
                "SELECT reported_version_text FROM product_source_records"
            ).scalar_one()
            == "3"
        )
        assert (
            connection.exec_driver_sql(
                "SELECT source_version_value FROM product_versions"
            ).scalar_one()
            == "3"
        )
        connection.exec_driver_sql(
            "UPDATE product_versions SET version_number=NULL, source_version_value='-1'"
        )
        with pytest.raises(RuntimeError, match="Downgrade refused"):
            migration.downgrade()
        assert "source_version_value" in {
            c["name"] for c in sa.inspect(connection).get_columns("product_versions")
        }
        connection.exec_driver_sql(
            "UPDATE product_versions SET version_number=3, source_version_value='3'"
        )
        migration.downgrade()
        assert connection.exec_driver_sql("SELECT * FROM product_versions").all() == [
            (1, 3)
        ]
    engine.dispose()
