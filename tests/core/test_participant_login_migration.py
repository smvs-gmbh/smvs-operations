import runpy

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.alert_desk.test_workspace import fixture_database
from app.core.db.models import Base

NAMES = {
    "alert_desk_login_tokens",
    "alert_desk_participant_sessions",
    "alert_desk_participant_passkeys",
    "alert_desk_login_throttles",
    "alert_desk_auth_events",
}


def test_participant_auth_migration_preserves_existing_data_and_retains_evidence(
    tmp_path,
):
    engine, _ = fixture_database(tmp_path / "migration.db")
    try:
        with engine.begin() as c:
            for name in NAMES:
                Base.metadata.tables[name].drop(c)
            migration = runpy.run_path("alembic/versions/0057_participant_login.py")
            context = MigrationContext.configure(
                c,
                opts={
                    "include_object": lambda obj, name, kind, reflected, compare_to: (
                        kind != "table" or name in NAMES
                    )
                },
            )
            migration["upgrade"].__globals__["op"] = Operations(context)
            migration["upgrade"]()
            assert compare_metadata(context, Base.metadata) == []
            c.execute(
                text(
                    "INSERT INTO alert_desk_auth_events (occurred_at,kind,data) VALUES ('2026-11-27','Test','{}')"
                )
            )
            with pytest.raises(
                RuntimeError, match="Retain participant authentication evidence"
            ):
                migration["downgrade"]()
            assert c.scalar(text("SELECT COUNT(*) FROM alert_desk_auth_events")) == 1
    finally:
        engine.dispose()
