import runpy
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, inspect, text

from app.alert_desk.test_workspace import create_workspace, fixture_database
from app.core.db.models import Base
from app.domain.models import AlertDeskCommentTemplate, AlertDeskCommentTemplateEvent


def test_template_migration_matches_models_and_preserves_existing_cases(tmp_path):
    engine, factory = fixture_database(tmp_path / "migration.db")
    create_workspace(factory)
    names = {
        AlertDeskCommentTemplate.__tablename__,
        AlertDeskCommentTemplateEvent.__tablename__,
    }
    try:
        with engine.begin() as connection:
            count = connection.scalar(text("SELECT COUNT(*) FROM nmvs_exceptions"))
            AlertDeskCommentTemplateEvent.__table__.drop(connection)
            AlertDeskCommentTemplate.__table__.drop(connection)
            migration = runpy.run_path(
                str(Path("alembic/versions/0055_comment_templates.py"))
            )
            context = MigrationContext.configure(
                connection,
                opts={
                    "include_object": lambda obj, name, kind, reflected, compare_to: (
                        kind != "table" or name in names
                    )
                },
            )
            migration["upgrade"].__globals__["op"] = Operations(context)
            migration["upgrade"]()
            expected = MetaData()
            for table in Base.metadata.sorted_tables:
                table.to_metadata(expected)
            assert compare_metadata(context, expected) == []
            assert (
                connection.scalar(text("SELECT COUNT(*) FROM nmvs_exceptions")) == count
            )
            migration["downgrade"]()
            assert not names.intersection(inspect(connection).get_table_names())
            assert (
                connection.scalar(text("SELECT COUNT(*) FROM nmvs_exceptions")) == count
            )
    finally:
        engine.dispose()
