import runpy

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.alert_desk.test_workspace import fixture_database
from app.core.db.models import Base
from app.domain.models import AlertDeskMailDelivery


def test_mail_migration_and_refusal_to_discard_delivery_evidence(tmp_path):
    engine, _ = fixture_database(tmp_path / "migration.db")
    try:
        with engine.begin() as c:
            AlertDeskMailDelivery.__table__.drop(c)
            migration = runpy.run_path("alembic/versions/0056_alert_desk_mail.py")
            context = MigrationContext.configure(c, opts={"include_object": lambda obj, name, kind, reflected, compare_to: kind != "table" or name == "alert_desk_mail_deliveries"})
            migration["upgrade"].__globals__["op"] = Operations(context)
            migration["upgrade"]()
            assert compare_metadata(context, Base.metadata) == []
            c.execute(text("INSERT INTO alert_desk_mail_deliveries (id,recipient,kind,template_id,fingerprint,attempted_at,status) VALUES ('test','test@example.test','test','d-test','hash','2026-11-26','accepted')"))
            with pytest.raises(RuntimeError, match="Retain delivery evidence"):
                migration["downgrade"]()
            assert c.scalar(text("SELECT COUNT(*) FROM alert_desk_mail_deliveries")) == 1
    finally:
        engine.dispose()
