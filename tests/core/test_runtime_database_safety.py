from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.core.db import engine as database_engine
from app.core.db.models import IntegrationJob
from app.core.db.safety import DatabaseSafetyError, assert_migration_database_safe
from app.core.db.session import GuardedSession
from app.integration.sources.nmvs.daily_snapshot import DailySnapshotAcquisition


@pytest.mark.parametrize("name", ["", "smvs", "SMVS_OPERATIONS", "smvs_operations "])
def test_invalid_configuration_is_rejected_before_engine_creation(monkeypatch, name):
    monkeypatch.setattr(database_engine, "get_settings", lambda: SimpleNamespace(db_name=name))
    create = Mock()
    monkeypatch.setattr(database_engine, "create_engine", create)
    with pytest.raises(DatabaseSafetyError):
        database_engine.create_database_engine()
    create.assert_not_called()
    selector = Mock()
    with pytest.raises(DatabaseSafetyError):
        assert_migration_database_safe(name, selector)
    selector.assert_not_called()


def database_double(selected):
    # In-memory SQL test double; never connects to a configured MySQL database.
    engine = create_engine("sqlite://")
    statements = []

    @event.listens_for(engine, "connect")
    def register(dbapi_connection, _):
        dbapi_connection.create_function("DATABASE", 0, selected)

    @event.listens_for(engine, "before_cursor_execute")
    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    return engine, statements


@pytest.mark.parametrize("selected", [None, "", "smvs", "SMVS_OPERATIONS"])
def test_wrong_selected_database_blocks_sql_and_poisoned_session_reuse(selected):
    engine, statements = database_double(lambda: selected)
    with GuardedSession(engine, configured_database="smvs_operations") as session:
        with pytest.raises(DatabaseSafetyError):
            session.execute(text("CREATE TABLE must_not_exist (id INTEGER)"))
        session.rollback()
        with pytest.raises(DatabaseSafetyError):
            session.execute(text("CREATE TABLE must_not_exist (id INTEGER)"))
    assert statements == ["SELECT DATABASE()"]
    engine.dispose()


def test_guard_rechecks_actual_connection_after_commit_rollback_and_reconnect():
    selected = ["smvs_operations"]
    engine, statements = database_double(lambda: selected[0])
    with GuardedSession(engine, configured_database="smvs_operations") as session:
        session.execute(text("SELECT 1"))
        session.commit()
        session.execute(text("SELECT 2"))
        session.rollback()
        engine.dispose()
        session.execute(text("SELECT 3"))
        session.commit()
        selected[0] = "smvs"
        with pytest.raises(DatabaseSafetyError):
            session.execute(text("SELECT 4"))
    assert statements == [
        "SELECT DATABASE()", "SELECT 1", "SELECT DATABASE()", "SELECT 2",
        "SELECT DATABASE()", "SELECT 3", "SELECT DATABASE()",
    ]
    engine.dispose()


def test_verification_errors_are_fail_closed_and_sanitized():
    def unavailable():
        raise RuntimeError("secret-token password=sensitive")

    engine, statements = database_double(unavailable)
    with (
        GuardedSession(engine, configured_database="smvs_operations") as session,
        pytest.raises(DatabaseSafetyError) as error,
    ):
        session.execute(text("SELECT 1"))
    assert "secret" not in str(error.value)
    assert error.value.__suppress_context__
    assert statements == ["SELECT DATABASE()"]
    engine.dispose()


def test_orm_flush_is_guarded_before_insert_and_failed_session_cannot_commit():
    engine, statements = database_double(lambda: "smvs")
    with GuardedSession(engine, configured_database="smvs_operations") as session:
        session.add(IntegrationJob(source_name="NMVS"))
        with pytest.raises(DatabaseSafetyError):
            session.flush()
        session.rollback()
        with pytest.raises(DatabaseSafetyError):
            session.commit()
    assert statements == ["SELECT DATABASE()"]
    engine.dispose()


def test_acquisition_refuses_unguarded_session_before_http_or_writes():
    client = Mock()
    with Session() as session, pytest.raises(DatabaseSafetyError):
        DailySnapshotAcquisition(client).run(session)
    assert not client.mock_calls
