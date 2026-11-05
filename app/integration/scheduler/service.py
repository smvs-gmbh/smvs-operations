from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select

from app.core.db.models import (
    ImportExecution,
    ImportMutex,
    ImportSchedule,
    IntegrationJob,
)
from app.core.db.session import require_runtime_session
from app.domain.models import ManualImportAttempt, ManualImportRequest
from app.integration.artifacts.storage import utcnow
from app.integration.failures import IntegrationExecutionError, sanitized_failure


def next_daily(now: datetime, daily_time: str, timezone: str) -> datetime:
    """First daily local wall-clock occurrence strictly after UTC-naive now.

    Nonexistent DST times move forward through the gap; ambiguous times use the
    first occurrence. UTC storage prevents running twice at the repeated hour.
    """
    if now.tzinfo is not None:
        raise ValueError("Scheduler clock must return UTC-naive values.")
    if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", daily_time):
        raise ValueError("Daily time requires HH:MM.")
    zone = ZoneInfo(timezone)
    local = now.replace(tzinfo=UTC).astimezone(zone)
    wall = time.fromisoformat(daily_time)
    for offset in range(3):
        candidate = datetime.combine(local.date() + timedelta(days=offset), wall, zone)
        instant = candidate.astimezone(UTC).replace(tzinfo=None)
        if instant > now:
            return instant
    raise ValueError("Could not calculate next daily execution.")


class ImportScheduler:
    def __init__(
        self,
        session_factory,
        handlers: dict[str, Callable[[], IntegrationJob]],
        clock=utcnow,
        backfill_handler=None,
    ):
        self.sessions, self.handlers, self.clock = session_factory, handlers, clock
        self.backfill_handler = backfill_handler

    def configure(
        self,
        key: str,
        *,
        daily_time="04:00",
        timezone="Europe/Zurich",
        enabled=False,
        interval_seconds=None,
    ):
        if key not in self.handlers:
            raise ValueError("Unknown import key.")
        if interval_seconds is not None and (
            isinstance(interval_seconds, bool)
            or not isinstance(interval_seconds, int)
            or not 60 <= interval_seconds <= 604800
        ):
            raise ValueError(
                "Import interval must be between one minute and seven days."
            )
        next_run = (
            self.clock() + timedelta(seconds=interval_seconds)
            if interval_seconds is not None
            else next_daily(self.clock(), daily_time, timezone)
        )
        with self.sessions() as session:
            require_runtime_session(session)
            schedule = session.scalar(
                select(ImportSchedule)
                .where(ImportSchedule.import_key == key)
                .with_for_update()
            )
            if schedule is None:
                session.add(ImportMutex(import_key=key))
                schedule = ImportSchedule(
                    import_key=key,
                    retry_count=0,
                    max_attempts=3,
                    retry_delay_seconds=300,
                )
                session.add(schedule)
            # Changing a schedule while its import is running is refused. Never
            # wait for a long-running import when configuring from another process.
            else:
                mutex = session.scalar(
                    select(ImportMutex)
                    .where(ImportMutex.import_key == key)
                    .with_for_update(skip_locked=True)
                )
                if mutex is None:
                    raise ValueError(
                        "Import is running; configure it after completion."
                    )
            schedule.daily_time, schedule.timezone = daily_time, timezone
            schedule.interval_seconds = interval_seconds
            schedule.enabled, schedule.next_run_at, schedule.retry_count = (
                schedule.enabled
                if enabled is None and schedule.enabled is not None
                else int(bool(enabled)),
                next_run,
                0,
            )
            session.commit()
            return schedule.id

    def set_enabled(self, key, enabled):
        if key not in self.handlers:
            raise ValueError("Unknown import key.")
        with self.sessions() as session:
            require_runtime_session(session)
            schedule = session.scalar(
                select(ImportSchedule)
                .where(ImportSchedule.import_key == key)
                .with_for_update()
            )
            if schedule is None:
                raise ValueError("Configure this import first.")
            if enabled and not schedule.enabled:
                schedule.next_run_at = (
                    self.clock() + timedelta(seconds=schedule.interval_seconds)
                    if schedule.interval_seconds is not None
                    else next_daily(
                        self.clock(), schedule.daily_time, schedule.timezone
                    )
                )
                schedule.retry_count = 0
            schedule.enabled = int(enabled)
            session.commit()

    def tick_manual(self):
        with self.sessions() as session:
            require_runtime_session(session)
            pending = session.execute(
                select(ManualImportRequest.id, ImportSchedule.import_key)
                .join(
                    ImportSchedule, ImportSchedule.id == ManualImportRequest.schedule_id
                )
                .where(
                    ManualImportRequest.status.in_(("queued", "running")),
                    (ManualImportRequest.retry_at.is_(None))
                    | (ManualImportRequest.retry_at <= self.clock()),
                )
                .order_by(ManualImportRequest.requested_at, ManualImportRequest.id)
                .limit(20)
            ).all()
        for identifier, key in pending:
            execution = self.execute(key, manual=True, request_id=identifier)
            if execution is not None:
                return [execution]
        return []

    def tick(self) -> list[int]:
        result = self.tick_manual()
        now = self.clock()
        with self.sessions() as session:
            require_runtime_session(session)
            orphan = exists(
                select(ImportExecution.id).where(
                    ImportExecution.schedule_id == ImportSchedule.id,
                    ImportExecution.status == "running",
                )
            )
            keys = session.scalars(
                select(ImportSchedule.import_key)
                .where(
                    (
                        (ImportSchedule.enabled == 1)
                        & (ImportSchedule.next_run_at <= now)
                    )
                    | orphan
                )
                .order_by(ImportSchedule.next_run_at)
            ).all()
        for key in keys:
            execution_id = self.execute(key)
            if execution_id is not None:
                result.append(execution_id)
        return result

    @staticmethod
    def _reschedule(schedule: ImportSchedule, now: datetime, failed: bool):
        if (
            schedule.interval_seconds is not None
            and not 60 <= schedule.interval_seconds <= 604800
        ):
            raise ValueError("Invalid import interval configuration.")
        if schedule.max_attempts < 1 or schedule.retry_delay_seconds < 1:
            raise ValueError("Invalid scheduler retry configuration.")
        if failed and schedule.retry_count + 1 < schedule.max_attempts:
            schedule.retry_count += 1
            schedule.next_run_at = now + timedelta(seconds=schedule.retry_delay_seconds)
        else:
            schedule.retry_count = 0
            schedule.next_run_at = (
                now + timedelta(seconds=schedule.interval_seconds)
                if schedule.interval_seconds is not None
                else next_daily(now, schedule.daily_time, schedule.timezone)
            )

    def execute(self, key: str, *, manual=False, request_id=None) -> int | None:
        if key not in self.handlers or request_id is not None and not manual:
            raise ValueError(
                "Unknown or invalid import execution. Request processing must be manual."
            )
        # Independent mutex row held across all importer transactions. A process
        # crash releases the DB lock. There is no time-based lease that can expire
        # during a healthy long-running import. No run/schedule FK points here.
        with self.sessions() as lock_session:
            require_runtime_session(lock_session)
            mutex = lock_session.scalar(
                select(ImportMutex)
                .where(ImportMutex.import_key == key)
                .with_for_update(skip_locked=True)
            )
            if mutex is None:
                return None
            with self.sessions() as session:
                require_runtime_session(session)
                schedule = session.scalar(
                    select(ImportSchedule)
                    .where(ImportSchedule.import_key == key)
                    .with_for_update()
                )
                if schedule is None:
                    raise ValueError("Import schedule is not configured.")
                now = self.clock()
                running = session.scalars(
                    select(ImportExecution).where(
                        ImportExecution.schedule_id == schedule.id,
                        ImportExecution.status == "running",
                    )
                ).all()
                if running:
                    # The source mutex is free: previous running attempts lost their worker.
                    scheduled_interrupted = False
                    for previous in running:
                        previous.status, previous.completed_at = "interrupted", now
                        previous.failure_code = "worker_interrupted"
                        previous.failure_message = "Previous worker stopped before recording completion; retry is idempotent."
                        attempt = session.get(ManualImportAttempt, previous.id)
                        if attempt:
                            orphan = session.get(
                                ManualImportRequest, attempt.request_id
                            )
                            if orphan.status == "running":
                                orphan.status = (
                                    "queued"
                                    if orphan.attempt_count < schedule.max_attempts
                                    else "failed"
                                )
                                orphan.retry_at = (
                                    now
                                    + timedelta(seconds=schedule.retry_delay_seconds)
                                    if orphan.status == "queued"
                                    else None
                                )
                                orphan.completed_at, orphan.last_error = (
                                    now,
                                    previous.failure_message,
                                )
                        else:
                            scheduled_interrupted = True
                    if scheduled_interrupted:
                        self._reschedule(schedule, now, failed=True)
                    session.commit()
                    if not manual:
                        return None
                task = None
                if request_id is not None:
                    task = session.scalar(
                        select(ManualImportRequest)
                        .where(ManualImportRequest.id == request_id)
                        .with_for_update()
                    )
                    if (
                        not task
                        or task.schedule_id != schedule.id
                        or task.status != "queued"
                        or task.retry_at is not None
                        and task.retry_at > now
                    ):
                        return None
                    if task.kind == "backfill":
                        from app.integration.scheduler.control import validate_period

                        validate_period(key, task.start_date, task.end_date)
                    task.status, task.retry_at = "running", None
                    task.attempt_count += 1
                    task.completed_at = None
                if not manual and (not schedule.enabled or schedule.next_run_at > now):
                    return None
                execution = ImportExecution(
                    schedule_id=schedule.id,
                    trigger="backfill"
                    if task and task.kind == "backfill"
                    else "manual"
                    if manual
                    else "schedule",
                    status="running",
                    started_at=now,
                )
                session.add(execution)
                session.flush()
                execution_id = execution.id
                backfill_dates = (
                    (task.start_date, task.end_date)
                    if task and task.kind == "backfill"
                    else None
                )
                if task:
                    session.add(
                        ManualImportAttempt(
                            execution_id=execution_id, request_id=task.id
                        )
                    )
                session.commit()  # Durable before invoking any source or import code.
            job_id, failure = None, None
            try:
                if backfill_dates is not None:
                    if self.backfill_handler is None:
                        raise ValueError("Backfill handler is unavailable.")
                    job = self.backfill_handler(key, *backfill_dates)
                else:
                    job = self.handlers[key]()
                job_id = job.id
                if job.status != "succeeded":
                    raise ValueError("Importer did not return a completed job.")
            except Exception as error:  # noqa: BLE001 - persist allowlisted diagnostics only
                if isinstance(error, IntegrationExecutionError):
                    job_id = error.job_id
                    if not error.processing_succeeded:
                        failure = (error.code, str(error))
                else:
                    failure = sanitized_failure(error)
            with self.sessions() as session:
                require_runtime_session(session)
                execution = session.get(ImportExecution, execution_id)
                schedule = session.get(ImportSchedule, execution.schedule_id)
                execution.integration_job_id = job_id
                execution.completed_at = self.clock()
                execution.status = "failed" if failure else "succeeded"
                if failure:
                    execution.failure_code, execution.failure_message = failure
                if request_id is not None:
                    task = session.get(ManualImportRequest, request_id)
                    task.completed_at = execution.completed_at
                    task.last_error = failure[1] if failure else None
                    task.status = (
                        (
                            "queued"
                            if task.attempt_count < schedule.max_attempts
                            else "failed"
                        )
                        if failure
                        else "succeeded"
                    )
                    task.retry_at = (
                        execution.completed_at
                        + timedelta(seconds=schedule.retry_delay_seconds)
                        if task.status == "queued"
                        else None
                    )
                # Backfill never modifies cadence, retry state or automatic next-run time.
                if backfill_dates is None:
                    self._reschedule(
                        schedule, execution.completed_at, failed=failure is not None
                    )
                session.commit()
            return execution_id
