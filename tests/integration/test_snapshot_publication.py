# ruff: noqa: F811
from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.db.models import AcquiredArtifact, ImportMutex, ProcessingRun
from app.domain.mapping import MappingError, publish
from app.domain.models import CurrentPublication, MappingRun, ParticipantPublication
from app.domain.participants.mapping import MUTEX
from app.integration.scheduler.publication import publish_snapshot
from tests.domain.test_mapping import seed, sessions  # noqa: F401
from tests.domain.test_participants import source


def job_for(factory, run_id):
    with factory() as session:
        return session.scalar(
            select(AcquiredArtifact.integration_job_id)
            .join(ProcessingRun, ProcessingRun.artifact_id == AcquiredArtifact.id)
            .where(ProcessingRun.id == run_id)
        )


def test_snapshot_publication_advances_working_sets_reuses_selected_sai_and_is_idempotent(
    sessions,
):
    with sessions.begin() as session:
        session.add(ImportMutex(import_key=MUTEX))
    initial, sai = seed(sessions)
    publish(sessions, initial, sai, "synthetic-nmvs")
    latest = source(sessions, day=date(2026, 11, 10))
    job_id = job_for(sessions, latest)
    first = publish_snapshot(sessions, job_id)
    assert publish_snapshot(sessions, job_id) == first
    with sessions() as session:
        current = session.get(CurrentPublication, "product-batch")
        run = session.get(MappingRun, current.mapping_run_id)
        participants = session.get(ParticipantPublication, "participants")
        assert current.snapshot_date == participants.snapshot_date == date(2026, 11, 10)
        assert run.sai_run_id == sai
        assert session.scalar(select(func.count()).select_from(MappingRun)) == 2
    with pytest.raises(MappingError):
        publish_snapshot(sessions, job_for(sessions, initial))
    with sessions() as session:
        assert session.get(CurrentPublication, "product-batch").snapshot_date == date(
            2026, 11, 10
        )


def test_initial_reference_selection_is_not_guessed(sessions):
    snapshot, _ = seed(sessions)
    with pytest.raises(ValueError, match="initial"):
        publish_snapshot(sessions, job_for(sessions, snapshot))


def test_manual_worker_mode_does_not_start_automatic_imports(monkeypatch):
    import sys
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.integration.scheduler import __main__ as cli

    scheduler = Mock()
    calls = []

    class Stop:
        def __init__(self):
            self.count = 0

        def is_set(self):
            self.count += 1
            return self.count > 1

        def set(self):
            pass

        def wait(self, seconds):
            pass

    @contextmanager
    def heartbeat(factory, *, mode):
        calls.append(mode)
        yield

    monkeypatch.setattr(sys, "argv", ["scheduler", "--serve-manual"])
    monkeypatch.setattr(cli, "ImportScheduler", lambda *args, **kwargs: scheduler)
    monkeypatch.setattr(cli, "worker_heartbeat", heartbeat)
    monkeypatch.setattr(cli, "threading", SimpleNamespace(Event=Stop))
    monkeypatch.setattr(cli.signal, "signal", lambda *args: None)
    monkeypatch.setattr("app.domain.pack_audit.service.tick", lambda factory: None)
    monkeypatch.setattr("app.domain.uploads.service.tick", lambda factory: None)
    cli.main()
    scheduler.tick_manual.assert_called_once()
    scheduler.tick.assert_not_called()
    assert calls == ["manual"]
