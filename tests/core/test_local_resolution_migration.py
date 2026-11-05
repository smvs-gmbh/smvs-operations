import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migrate_reviewed_without_claiming_a_new_resolution():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/0018_local_resolution.py"
    )
    spec = importlib.util.spec_from_file_location("local_resolution", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE exception_reviews (id INTEGER PRIMARY KEY, status VARCHAR(20), review_reason TEXT)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO exception_reviews VALUES (1,'reviewed','Original reason'), (2,'to_do','Pending')"
            )
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        table = sa.Table("exception_reviews", sa.MetaData(), autoload_with=connection)
        rows = (
            connection.execute(sa.select(table).order_by(table.c.id)).mappings().all()
        )
        assert rows[0]["status"] == "resolved"
        assert rows[0]["review_reason"] == "Original reason"
        assert rows[0]["resolution"]["basis"] == "legacy_reviewed"
        assert rows[1]["status"] == "to_do" and rows[1]["resolution"] is None
        migration.downgrade()
        assert (
            connection.execute(
                sa.text("SELECT status FROM exception_reviews WHERE id=1")
            ).scalar_one()
            == "reviewed"
        )
