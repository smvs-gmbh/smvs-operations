# ruff: noqa: DTZ001 -- database clocks intentionally use UTC-naive datetimes
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.core.db.models import Base, ImportExecution, ImportSchedule, IntegrationJob
from app.core.db.session import GuardedSession
from app.integration.scheduler.service import ImportScheduler, next_daily


@pytest.mark.parametrize(
    "now,wall,expected",
    [
        (datetime(2026, 11, 4, 2), "04:00", datetime(2026, 11, 4, 3)),
        (datetime(2026, 11, 4, 3), "04:00", datetime(2026, 11, 5, 3)),
        (datetime(2026, 3, 28, 4), "04:00", datetime(2026, 3, 29, 2)),
        (datetime(2026, 3, 28, 4), "02:30", datetime(2026, 3, 29, 1, 30)),
        (datetime(2026, 10, 24, 4), "02:30", datetime(2026, 10, 25, 0, 30)),
        (datetime(2026, 10, 25, 1), "02:30", datetime(2026, 10, 26, 1, 30)),
    ],
)
def test_daily_clock_and_dst(now, wall, expected):
    assert next_daily(now, wall, "Europe/Zurich") == expected


@pytest.mark.parametrize("wall", ["24:00", "4:00", "03:60", "bad"])
def test_invalid_wall_clock(wall):
    with pytest.raises(ValueError):
        next_daily(datetime(2026, 11, 4), wall, "Europe/Zurich")


@pytest.fixture
def setup(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "scheduler.db"))

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.create_function("DATABASE", 0, lambda: "smvs_operations")

    Base.metadata.create_all(engine)
    factory = sessionmaker(
        engine,
        class_=GuardedSession,
        configured_database="smvs_operations",
        expire_on_commit=False,
    )
    clock = [datetime(2026, 11, 4, 2)]
    calls = []

    def handler():
        calls.append(clock[0])
        with factory() as s:
            job = IntegrationJob(
                source_name="Synthetic",
                channel_name="test",
                report_type="test",
                status="succeeded",
                created_at=clock[0],
            )
            s.add(job)
            s.commit()
            return job

    scheduler = ImportScheduler(factory, {"sai": handler}, clock=lambda: clock[0])
    scheduler.configure("sai", enabled=True)
    yield scheduler, factory, clock, calls
    engine.dispose()


def test_due_only_once_and_coalesces_downtime(setup):
    scheduler, factory, clock, calls = setup
    assert scheduler.tick() == []
    clock[0] = datetime(2026, 11, 8, 4)
    assert len(scheduler.tick()) == 1
    assert scheduler.tick() == []
    assert len(calls) == 1
    with factory() as s:
        execution = s.scalar(select(ImportExecution))
        assert execution.status == "succeeded"
        assert execution.integration_job_id is not None
        assert s.scalar(select(ImportSchedule)).next_run_at == datetime(2026, 11, 9, 3)


def test_manual_uses_same_execution_path_and_can_run_disabled_schedule(setup):
    scheduler, factory, _clock, calls = setup
    scheduler.configure("sai", enabled=False)
    assert scheduler.tick() == []
    assert scheduler.execute("sai", manual=True)
    with factory() as s:
        assert s.scalar(select(ImportExecution)).trigger == "manual"
    assert len(calls) == 1


def test_failure_retry_budget_and_sanitized_diagnostics(setup):
    scheduler, factory, clock, _calls = setup

    def fail():
        raise RuntimeError("SECRET must not be saved")

    scheduler.handlers["sai"] = fail
    clock[0] = datetime(2026, 11, 4, 3)
    for attempt in range(3):
        assert scheduler.tick()
        with factory() as s:
            schedule = s.scalar(select(ImportSchedule))
            assert (
                s.scalar(
                    select(ImportExecution).order_by(ImportExecution.id.desc())
                ).status
                == "failed"
            )
            assert schedule.retry_count == (attempt + 1 if attempt < 2 else 0)
            for execution in s.scalars(select(ImportExecution)):
                assert "SECRET" not in execution.failure_message
        if attempt < 2:
            assert scheduler.tick() == []
            clock[0] += timedelta(minutes=5)
    assert scheduler.tick() == []
    with factory() as s:
        assert s.scalar(select(ImportSchedule)).next_run_at == datetime(2026, 11, 5, 3)


def test_orphaned_execution_recovered_after_restart(setup):
    scheduler, factory, clock, calls = setup
    with factory() as s:
        schedule = s.scalar(select(ImportSchedule))
        s.add(
            ImportExecution(
                schedule_id=schedule.id,
                trigger="schedule",
                status="running",
                started_at=clock[0],
            )
        )
        s.commit()
    # The DB mutex is free: this durable running record belongs to a stopped worker.
    assert scheduler.tick() == []
    with factory() as s:
        assert s.scalar(select(ImportExecution)).status == "interrupted"
    clock[0] += timedelta(minutes=5)
    restarted = ImportScheduler(factory, scheduler.handlers, clock=lambda: clock[0])
    assert restarted.tick()
    assert len(calls) == 1


def test_new_process_uses_persisted_schedule(setup):
    scheduler, factory, clock, _calls = setup
    clock[0] = datetime(2026, 11, 4, 3)
    restarted = ImportScheduler(factory, scheduler.handlers, clock=lambda: clock[0])
    assert restarted.tick()
    assert scheduler.tick() == []


def test_missing_handler_is_refused(setup):
    scheduler, _, _, _ = setup
    with pytest.raises(ValueError):
        scheduler.configure("unknown")
    with pytest.raises(ValueError):
        scheduler.execute("unknown", manual=True)
