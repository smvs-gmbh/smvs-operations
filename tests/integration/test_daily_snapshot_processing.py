from datetime import date
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.db.models import (
    AcquiredArtifact,
    ArtifactContent,
    Base,
    IntegrationJob,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.core.db.safety import DatabaseSafetyError
from app.core.db.session import GuardedSession
from app.integration.failures import IntegrationExecutionError, sanitized_failure
from app.integration.sources.nmvs import processing
from app.integration.sources.nmvs.daily_snapshot import DailySnapshotAcquisition
from app.integration.sources.nmvs.parsing import (
    DailySnapshotParseError,
    parse_daily_snapshot,
)
from app.integration.sources.nmvs.processing import replay_daily_snapshot
from app.integration.sources.nmvs.reporting import (
    DailySnapshotResponse,
    ReportingApiError,
)

VALID = b"Report Type,DailySnapshot\n\nProducts\nCode\n001\n002\n\nEmpty\nHeader\n"
SENSITIVE = "Authorization: Bearer private-token password=secret https://user:pw@example.test/report?sig=private-key"


@pytest.fixture
def database():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def database_double(connection, _):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.create_function("DATABASE", 0, lambda: "smvs_operations")

    @event.listens_for(engine, "begin")
    def explicit_transactions(connection):
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(database):
    with GuardedSession(database, configured_database="smvs_operations", expire_on_commit=False, autoflush=False) as session:
        yield session


def client(content=VALID):
    value = Mock(api_version="1")
    value.get_daily_snapshot.return_value = DailySnapshotResponse(
        report_uri="/reports/daily", report_metadata={"id": "daily"}, content=content,
        content_type="text/csv", requested_api_version="1", used_api_version="1",
    )
    return value


def counts(session):
    return {model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (IntegrationJob, AcquiredArtifact, ArtifactContent, ProcessingRun, StagingDataset, StagingRow)}


def test_success_and_identical_reacquisition_have_separate_lineage(session, database):
    source = client()
    service = DailySnapshotAcquisition(source)
    first = service.run(session, days_in_past=1, today=date(2026, 9, 26))
    second = service.run(session, days_in_past=1, today=date(2026, 9, 26))
    assert first.status == second.status == "succeeded"
    assert first.id != second.id
    assert first.requested_snapshot_date == date(2026, 9, 25)
    assert source.get_daily_snapshot.call_count == 2
    with Session(database) as observer:
        acquisitions = observer.scalars(select(AcquiredArtifact).order_by(AcquiredArtifact.id)).all()
        runs = observer.scalars(select(ProcessingRun).order_by(ProcessingRun.id)).all()
        assert acquisitions[0].content_id == acquisitions[1].content_id
        assert [a.integration_job_id for a in acquisitions] == [first.id, second.id]
        assert [r.artifact_id for r in runs] == [a.id for a in acquisitions]
        assert all(r.status == "succeeded" and r.completed_at for r in runs)
        assert counts(observer) == {
            "integration_jobs": 2, "acquired_artifacts": 2, "artifact_contents": 1,
            "processing_runs": 2, "staging_datasets": 4, "staging_rows": 4,
        }


def test_parse_failure_is_durable_and_replay_uses_existing_bytes(session, database, monkeypatch):
    source = client(b"malformed metadata")
    with pytest.raises(IntegrationExecutionError) as failure:
        DailySnapshotAcquisition(source).run(session)
    assert failure.value.failure_recorded
    assert failure.value.stage == "extraction"
    with Session(database) as observer:
        run = observer.get(ProcessingRun, failure.value.processing_run_id)
        job = observer.get(IntegrationJob, failure.value.job_id)
        artifact = observer.get(AcquiredArtifact, run.artifact_id)
        artifact_id = artifact.id
        content_id = artifact.content_id
        assert run.status == job.status == "failed"
        assert run.failure_stage == job.failure_stage == "extraction"
        assert run.failure_code == "parse_error"
        assert artifact.artifact_bytes == b"malformed metadata"
        assert counts(observer)["staging_rows"] == 0

    def improved_parser(data):
        assert data == b"malformed metadata"
        return parse_daily_snapshot(VALID)

    monkeypatch.setattr(processing, "parse_daily_snapshot", improved_parser)
    source.get_daily_snapshot.side_effect = AssertionError("Replay must not acquire")
    replay = replay_daily_snapshot(session, artifact_id, parser_version="parser-2")
    assert replay.status == "succeeded" and replay.run_type == "replay"
    assert replay.parser_version == "parser-2"
    assert source.get_daily_snapshot.call_count == 1
    with Session(database) as observer:
        assert observer.get(IntegrationJob, failure.value.job_id).status == "failed"
        assert observer.get(ProcessingRun, failure.value.processing_run_id).status == "failed"
        artifact = observer.get(AcquiredArtifact, artifact_id)
        assert artifact.content_id == content_id and artifact.processing_status == "staged"
        assert counts(observer) == {
            "integration_jobs": 1, "acquired_artifacts": 1, "artifact_contents": 1,
            "processing_runs": 2, "staging_datasets": 2, "staging_rows": 2,
        }


def test_staging_failure_rolls_back_rows_and_preserves_prior_success_on_replay(session, database, monkeypatch):
    job = DailySnapshotAcquisition(client()).run(session)
    job_id = job.id
    with Session(database) as observer:
        artifact_id = observer.scalar(select(AcquiredArtifact.id))
        old_rows = observer.scalars(select(StagingRow.id)).all()
    original = processing.stage_daily_snapshot

    def stage_then_fail(*args, **kwargs):
        original(*args, **kwargs)  # Real INSERTs and flush, then fail.
        raise RuntimeError(SENSITIVE)

    monkeypatch.setattr(processing, "stage_daily_snapshot", stage_then_fail)
    with pytest.raises(IntegrationExecutionError) as failure:
        replay_daily_snapshot(session, artifact_id)
    assert failure.value.stage == "staging" and failure.value.failure_recorded
    assert "private" not in str(failure.value)
    assert failure.value.__suppress_context__
    with Session(database) as observer:
        assert observer.scalars(select(StagingRow.id)).all() == old_rows
        assert observer.get(IntegrationJob, job_id).status == "succeeded"
        assert observer.get(AcquiredArtifact, artifact_id).processing_status == "staged"
        runs = observer.scalars(select(ProcessingRun).order_by(ProcessingRun.id)).all()
        assert [run.status for run in runs] == ["succeeded", "failed"]
        assert runs[1].failure_stage == "staging" and runs[1].completed_at
        assert runs[1].failure_message == "The integration operation failed."
        assert counts(observer)["staging_datasets"] == 2


def test_failed_success_commit_rolls_back_all_staging_and_success_markers(session, database, monkeypatch):
    commit = session.commit

    def fail_success_commit():
        if any(isinstance(obj, ProcessingRun) and obj.status == "succeeded" for obj in session.dirty):
            raise OperationalError("statement", {"token": "private"}, RuntimeError(SENSITIVE))
        commit()

    monkeypatch.setattr(session, "commit", fail_success_commit)
    with pytest.raises(IntegrationExecutionError) as failure:
        DailySnapshotAcquisition(client()).run(session)
    assert failure.value.failure_recorded
    with Session(database) as observer:
        run = observer.get(ProcessingRun, failure.value.processing_run_id)
        job = observer.get(IntegrationJob, failure.value.job_id)
        assert run.status == job.status == "failed"
        assert run.failure_stage == "staging" and run.failure_code == "database_error"
        assert counts(observer)["staging_rows"] == counts(observer)["staging_datasets"] == 0
        assert observer.scalar(select(AcquiredArtifact)).artifact_bytes == VALID


def test_acquisition_failure_records_safe_job_error_without_fake_artifact_or_run(session, database):
    source = client()
    source.get_daily_snapshot.side_effect = httpx.ConnectError(SENSITIVE)
    with pytest.raises(IntegrationExecutionError) as failure:
        DailySnapshotAcquisition(source).run(session)
    assert failure.value.failure_recorded and failure.value.processing_run_id is None
    with Session(database) as observer:
        job = observer.get(IntegrationJob, failure.value.job_id)
        assert job.status == "failed" and job.failure_stage == "acquisition"
        assert job.failure_code == "http_error"
        assert job.failure_message == "The source HTTP request failed."
        assert counts(observer)["acquired_artifacts"] == counts(observer)["processing_runs"] == 0


def test_artifact_save_failure_does_not_leave_orphan_content(session, database):
    from app.integration.artifacts.storage import MySQLArtifactStore

    class FailingStore(MySQLArtifactStore):
        def save_daily_snapshot(self, *args):
            super().save_daily_snapshot(*args)
            raise RuntimeError(SENSITIVE)

    with pytest.raises(IntegrationExecutionError) as failure:
        DailySnapshotAcquisition(client(), artifact_store=FailingStore()).run(session)
    assert failure.value.failure_recorded
    with Session(database) as observer:
        assert observer.get(IntegrationJob, failure.value.job_id).failure_stage == "acquisition"
        assert counts(observer)["acquired_artifacts"] == counts(observer)["artifact_contents"] == 0


def test_lost_commit_acknowledgement_does_not_relabel_committed_staging_as_failed(session, database, monkeypatch):
    commit = session.commit

    def lost_acknowledgement():
        finishing = any(isinstance(obj, ProcessingRun) and obj.status == "succeeded" for obj in session.dirty)
        commit()
        if finishing:
            raise OperationalError("COMMIT", {}, RuntimeError(SENSITIVE))

    monkeypatch.setattr(session, "commit", lost_acknowledgement)
    with pytest.raises(IntegrationExecutionError) as failure:
        DailySnapshotAcquisition(client()).run(session)
    assert failure.value.processing_succeeded
    assert "completion was verified" in str(failure.value)
    with Session(database) as observer:
        assert observer.get(ProcessingRun, failure.value.processing_run_id).status == "succeeded"
        assert observer.get(IntegrationJob, failure.value.job_id).status == "succeeded"
        assert counts(observer)["staging_rows"] == 2


def test_unavailable_failure_recording_is_explicit_and_does_not_leak(session, database, monkeypatch):
    commit = session.commit

    def reject_failure_write():
        if any(isinstance(obj, ProcessingRun) and obj.status == "failed" for obj in session.dirty):
            raise OperationalError("statement", {"password": "secret"}, RuntimeError(SENSITIVE))
        commit()

    monkeypatch.setattr(session, "commit", reject_failure_write)
    with pytest.raises(IntegrationExecutionError) as failure:
        DailySnapshotAcquisition(client(b"bad")).run(session)
    assert not failure.value.failure_recorded
    assert "could not be durably recorded" in str(failure.value)
    assert "private" not in str(failure.value)
    with Session(database) as observer:
        assert observer.get(ProcessingRun, failure.value.processing_run_id).status == "extracting"
        assert counts(observer)["staging_rows"] == 0


@pytest.mark.parametrize("error,code", [
    (RuntimeError(SENSITIVE), "processing_error"),
    (ValueError(SENSITIVE), "invalid_data"),
    (DailySnapshotParseError(SENSITIVE), "parse_error"),
    (ReportingApiError(SENSITIVE), "reporting_api_error"),
    (DatabaseSafetyError(SENSITIVE), "database_safety"),
    (httpx.ConnectError(SENSITIVE), "http_error"),
    (OperationalError("statement", {"password": "secret"}, RuntimeError(SENSITIVE)), "database_error"),
])
def test_error_diagnostics_never_include_exception_details(error, code):
    actual_code, message = sanitized_failure(error)
    assert actual_code == code
    assert not any(value in message for value in ("private", "secret", "https:", "Bearer", "Authorization", "password"))


def test_unknown_exception_is_not_rendered():
    class HostileError(Exception):
        def __str__(self):
            raise AssertionError("Must not render untrusted exception text")

    assert sanitized_failure(HostileError()) == ("processing_error", "The integration operation failed.")


def test_replay_refuses_unguarded_or_busy_session(session):
    with Session() as unsafe, pytest.raises(DatabaseSafetyError):
        replay_daily_snapshot(unsafe, 1)
    session.add(IntegrationJob(source_name="uncommitted caller work"))
    with pytest.raises(ValueError, match="without an active transaction"):
        replay_daily_snapshot(session, 1)
    assert session.new  # Does not commit or roll back unrelated caller work.


def test_replay_unknown_id_has_no_acquisition_or_processing_side_effects(session, database):
    with pytest.raises(IntegrationExecutionError) as failure:
        replay_daily_snapshot(session, 999)
    assert failure.value.stage == "processing_start"
    with Session(database) as observer:
        assert all(value == 0 for value in counts(observer).values())


def test_default_expiring_guarded_session_is_supported(database):
    with GuardedSession(database, configured_database="smvs_operations") as session:
        job = DailySnapshotAcquisition(client()).run(session)
        assert job.status == "succeeded"
