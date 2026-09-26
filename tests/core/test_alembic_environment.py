import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, event, text

from alembic import context
from app.core import config
from app.core.db import engine as database_engine
from app.core.db.safety import DatabaseSafetyError

ENV = Path(__file__).resolve().parents[2] / "alembic" / "env.py"


def environment(monkeypatch, offline, configured="smvs_operations"):
    monkeypatch.setattr(context, "config", Config(), raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: offline)
    settings = Mock(return_value=SimpleNamespace(db_name=configured))
    monkeypatch.setattr(config, "get_settings", settings)
    return settings


def test_offline_mode_refuses_before_settings_or_engine(monkeypatch):
    settings = environment(monkeypatch, True)
    create = Mock()
    monkeypatch.setattr(database_engine, "create_database_engine", create)
    with pytest.raises(RuntimeError, match="Offline migrations are disabled"):
        runpy.run_path(str(ENV))
    settings.assert_not_called()
    create.assert_not_called()


def test_online_invalid_configuration_refuses_before_engine(monkeypatch):
    environment(monkeypatch, False, "smvs")
    create = Mock()
    monkeypatch.setattr(database_engine, "create_database_engine", create)
    with pytest.raises(DatabaseSafetyError):
        runpy.run_path(str(ENV))
    create.assert_not_called()


@pytest.mark.parametrize("selected", [None, "smvs", "smvs_operations"])
@pytest.mark.parametrize("migration_fails", [False, True])
def test_online_guard_and_outer_transaction_commit_or_rollback(monkeypatch, selected, migration_fails):
    environment(monkeypatch, False)
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def register(connection, _):
        connection.create_function("DATABASE", 0, lambda: selected)

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE version_double (revision TEXT)"))
    monkeypatch.setattr(database_engine, "create_database_engine", lambda: engine)
    configured = []

    def configure(connection, **kwargs):
        configured.append(MigrationContext.configure(connection))

    def migrate():
        configured[0].connection.execute(text("INSERT INTO version_double VALUES ('0001')"))
        if migration_fails:
            raise RuntimeError("simulated migration failure")

    runner = Mock(side_effect=migrate)
    monkeypatch.setattr(context, "configure", configure)
    monkeypatch.setattr(context, "begin_transaction", lambda: configured[0].begin_transaction())
    monkeypatch.setattr(context, "run_migrations", runner)
    if selected != "smvs_operations":
        with pytest.raises(DatabaseSafetyError):
            runpy.run_path(str(ENV))
        assert not configured
        runner.assert_not_called()
    elif migration_fails:
        with pytest.raises(RuntimeError, match="simulated migration failure"):
            runpy.run_path(str(ENV))
    else:
        runpy.run_path(str(ENV))
    with engine.connect() as connection:
        revisions = connection.execute(text("SELECT revision FROM version_double")).scalars().all()
    assert revisions == (["0001"] if selected == "smvs_operations" and not migration_fails else [])
    engine.dispose()
