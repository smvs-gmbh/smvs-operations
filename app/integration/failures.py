from __future__ import annotations

from typing import NoReturn

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db.models import AcquiredArtifact, IntegrationJob, ProcessingRun
from app.core.db.safety import DatabaseSafetyError
from app.core.db.session import require_runtime_session
from app.integration.artifacts.storage import utcnow
from app.integration.sources.nmvs.parsing import DailySnapshotParseError
from app.integration.sources.nmvs.reporting import ReportingApiError


class IntegrationExecutionError(RuntimeError):
    """Public, sanitized failure; never contains the original exception text."""

    def __init__(self, stage: str, code: str, message: str, recorded: bool,
                 job_id: int | None, processing_run_id: int | None, processing_succeeded: bool = False) -> None:
        self.stage = stage
        self.code = code
        self.failure_recorded = recorded
        self.job_id = job_id
        self.processing_run_id = processing_run_id
        self.processing_succeeded = processing_succeeded
        suffix = "" if recorded else " Failure could not be durably recorded."
        if processing_succeeded:
            suffix = " Processing completion was verified; do not automatically retry."
        super().__init__(f"{stage}: {message}{suffix}")


def sanitized_failure(error: Exception) -> tuple[str, str]:
    # Allowlisted diagnostics: do not render exception strings, repr, URLs,
    # response bodies, SQL parameters, or even user-defined exception names.
    categories = (
        (DatabaseSafetyError, "database_safety", "Database safety verification failed."),
        (DailySnapshotParseError, "parse_error", "The Daily Snapshot could not be parsed."),
        (ReportingApiError, "reporting_api_error", "The Reporting API response was unusable."),
        (httpx.HTTPError, "http_error", "The source HTTP request failed."),
        (SQLAlchemyError, "database_error", "The database operation failed."),
        (ValueError, "invalid_data", "The supplied data failed validation."),
    )
    for exception_type, code, message in categories:
        if isinstance(error, exception_type):
            return code, message
    return "processing_error", "The integration operation failed."


def fail_execution(session: Session, error: Exception, stage: str, *, job_id: int | None = None,
                   artifact_id: int | None = None, processing_run_id: int | None = None) -> NoReturn:
    code, message = sanitized_failure(error)
    recorded = False
    processing_succeeded = False
    try:
        session.rollback()
        require_runtime_session(session)
        # Reads and writes start a fresh transaction and repeat the database guard.
        run = session.get(ProcessingRun, processing_run_id) if processing_run_id is not None else None
        job = session.get(IntegrationJob, job_id) if job_id is not None else None
        if run is not None and run.status == "succeeded":
            # The server may have committed before the client lost the acknowledgement.
            # Do not label durable complete staging data as a failed attempt.
            processing_succeeded = True
            session.rollback()
        else:
            for record in (run, job):
                if record is not None:
                    record.status = "failed"
                    record.completed_at = utcnow()
                    record.failure_stage = stage
                    record.failure_code = code
                    record.failure_message = message
            if artifact_id is not None and run is not None:
                artifact = session.get(AcquiredArtifact, artifact_id)
                if artifact is not None:
                    prior_success = session.scalar(select(ProcessingRun.id).where(
                        ProcessingRun.artifact_id == artifact_id, ProcessingRun.status == "succeeded",
                    ).limit(1))
                    artifact.processing_status = "staged" if prior_success is not None else "failed"
            session.commit()
            recorded = run is not None if processing_run_id is not None else job is not None
    except Exception:  # noqa: BLE001 - failure reporting must not expose driver exceptions
        try:
            session.rollback()
        except Exception:  # noqa: BLE001, S110 - report safely below, never log driver text
            pass
    raise IntegrationExecutionError(
        stage, code, message, recorded, job_id, processing_run_id, processing_succeeded,
    ) from None


def require_idle_runtime_session(session: Session) -> None:
    require_runtime_session(session)
    if session.in_transaction():
        raise ValueError("Acquisition and replay require a session without an active transaction.")
