from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.core.db.models import ImportExecution, ImportMutex, ImportSchedule
from app.domain.models import (
    ManualImportAttempt,
    ManualImportRequest,
    SchedulerHeartbeat,
)
from app.integration.scheduler import control
from app.integration.scheduler.heartbeat import worker_heartbeat
from tests.integration.test_scheduler import setup  # noqa: F401


@pytest.fixture
def controlled(setup):  # noqa: F811
    _scheduler, factory, _clock, _calls = setup
    with factory() as s:
        s.add(ImportMutex(import_key=control.QUEUE_LOCK))
        s.commit()
    return setup


def test_duplicate_manual_clicks_paused_execution_and_attempt_link(controlled):
    scheduler, factory, _clock, calls = controlled
    scheduler.configure("sai", enabled=False)
    first = control.enqueue(factory, "sai")
    assert control.enqueue(factory, "sai").id == first.id
    assert scheduler.tick_manual()
    with factory() as s:
        task = s.get(ManualImportRequest, first.id)
        assert task.status == "succeeded" and task.attempt_count == 1
        assert not s.scalar(select(ImportSchedule)).enabled
        assert s.scalar(select(func.count()).select_from(ManualImportAttempt)) == 1
    assert scheduler.tick_manual() == [] and len(calls) == 1


def test_backfill_keeps_next_run_and_enabled_state(controlled):
    scheduler, factory, _clock, _calls = controlled
    scheduler.handlers["user_activity"] = scheduler.handlers["sai"]
    scheduler.configure("user_activity", enabled=True)
    scheduler.backfill_handler = lambda key, a, b: scheduler.handlers[key]()
    with factory() as s:
        before = s.scalar(
            select(ImportSchedule.next_run_at).where(
                ImportSchedule.import_key == "user_activity"
            )
        )
    task = control.enqueue(
        factory,
        "user_activity",
        kind="backfill",
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
    )
    scheduler.tick_manual()
    with factory() as s:
        schedule = s.scalar(
            select(ImportSchedule).where(ImportSchedule.import_key == "user_activity")
        )
        assert schedule.next_run_at == before and schedule.enabled
        assert s.get(ManualImportRequest, task.id).status == "succeeded"
        assert s.scalar(select(ImportExecution)).trigger == "backfill"


def test_pause_during_running_import_preserves_completion(controlled):
    scheduler, factory, clock, _calls = controlled
    original = scheduler.handlers["sai"]

    def handler():
        scheduler.set_enabled("sai", False)
        assert control.enqueue(factory, "sai") is None
        return original()

    scheduler.handlers["sai"] = handler
    clock[0] += timedelta(hours=1)
    assert scheduler.tick()
    with factory() as s:
        assert not s.scalar(select(ImportSchedule)).enabled
        assert s.scalar(select(ImportExecution)).status == "succeeded"
    assert scheduler.tick() == []
    scheduler.set_enabled("sai", True)
    with factory() as s:
        assert s.scalar(select(ImportSchedule)).next_run_at > clock[0]


def test_manual_retry_budget_and_safe_error(controlled):
    scheduler, factory, clock, _calls = controlled
    scheduler.set_enabled("sai", False)

    def broken():
        raise RuntimeError("SECRET VALUE")

    scheduler.handlers["sai"] = broken
    task = control.enqueue(factory, "sai")
    for i in range(3):
        assert scheduler.tick_manual()
        with factory() as s:
            current = s.get(ManualImportRequest, task.id)
            assert current.attempt_count == i + 1 and "SECRET" not in current.last_error
            assert current.status == ("queued" if i < 2 else "failed")
        assert scheduler.tick_manual() == []
        clock[0] += timedelta(minutes=5)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(ManualImportAttempt)) == 3


def test_orphaned_manual_request_is_recovered_and_cancelled_requests_stay_idle(
    controlled,
):
    scheduler, factory, clock, calls = controlled
    task = control.enqueue(factory, "sai")
    with factory() as s:
        t = s.get(ManualImportRequest, task.id)
        t.status = "running"
        t.attempt_count = 1
        execution = ImportExecution(
            schedule_id=t.schedule_id,
            status="running",
            trigger="manual",
            started_at=clock[0],
        )
        s.add(execution)
        s.flush()
        s.add(ManualImportAttempt(request_id=t.id, execution_id=execution.id))
        s.commit()
    assert scheduler.tick_manual() == []
    with factory() as s:
        assert s.get(ManualImportRequest, task.id).status == "queued"
        assert s.scalar(select(ImportExecution)).status == "interrupted"
    clock[0] += timedelta(minutes=5)
    assert scheduler.tick_manual() and len(calls) == 1
    again = control.enqueue(factory, "sai")
    control.cancel(factory, again.id)
    assert scheduler.tick_manual() == []
    with pytest.raises(ValueError):
        control.cancel(factory, task.id)


@pytest.mark.parametrize(
    "key,a,b",
    [
        ("sai", date(2026, 8, 1), date(2026, 8, 1)),
        ("user_activity", date(2026, 8, 1), date(2026, 9, 1)),
        ("user_activity", date(2026, 11, 4), date(2026, 11, 4)),
        ("pack_uploads", date(2026, 11, 4), date(2026, 11, 4)),
        ("exceptions", date(2026, 11, 5), date(2026, 11, 5)),
        ("daily_snapshot", date(2026, 8, 1), date(2026, 8, 2)),
    ],
)
def test_invalid_source_specific_windows(key, a, b):
    with pytest.raises(ValueError):
        control.validate_period(key, a, b, today=date(2026, 11, 4))


def test_heartbeat_is_fresh_during_worker_context_and_stopped_after_exit(controlled):
    _, factory, _, _ = controlled
    with worker_heartbeat(factory) as identifier, factory() as s:
        assert s.get(SchedulerHeartbeat, identifier).status == "running"
    with factory() as s:
        assert s.get(SchedulerHeartbeat, identifier).status == "stopped"
