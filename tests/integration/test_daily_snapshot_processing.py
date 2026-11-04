import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import create_engine, event, func, select, text
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

VALID = (
    b'"Report Type","Report Name","Date Requested (UTC)"\r\n'
    b'"Daily Snapshot","Synthetic","2024-02-29T00:00:00Z"\r\n\r\n'
    b'"Products"\r\n"Code"\r\n"001"\r\n"002"\r\n\r\n"Empty"\r\n"Header"\r\n'
)
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
        assert runs[1].reused_from_run_id == runs[0].id
        assert counts(observer) == {
            "integration_jobs": 2, "acquired_artifacts": 2, "artifact_contents": 1,
            "processing_runs": 2, "staging_datasets": 2, "staging_rows": 2,
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
        replay_daily_snapshot(session, artifact_id, parser_version="failure-test-next-parser")
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


@pytest.mark.parametrize("today,target", [
    (date(2025, 6, 16), date(2025, 6, 15)),
    (date(2025, 5, 1), date(2025, 4, 30)),
    (date(2026, 1, 1), date(2025, 12, 31)),
    (date(2024, 3, 1), date(2024, 2, 29)),
])
def test_acquisition_stores_actual_utc_request_bounds(session, database, today, target):
    source = client()
    job = DailySnapshotAcquisition(source).run(session, days_in_past=1, today=today)
    source.get_daily_snapshot.assert_called_once_with(target, target)
    with Session(database) as observer:
        stored = observer.get(IntegrationJob, job.id)
        assert stored.requested_snapshot_date == target
        assert stored.from_date == datetime(target.year, target.month, target.day, 0, 0, 0, tzinfo=UTC).replace(tzinfo=None)
        assert stored.to_date == datetime(target.year, target.month, target.day, 23, 59, 59, tzinfo=UTC).replace(tzinfo=None)


@pytest.mark.parametrize("content,content_type", [
    (VALID + b'"\xff"\r\n', "text/csv"),
    (VALID + b'"unclosed', "text/csv"),
    (VALID + b'"too","many"\r\n', "text/csv"),
    (VALID.replace(b'"Code"', b'"Code","Code"'), "text/csv"),
    (VALID.replace(b'"Code"', b'"Code","Other"'), "text/csv"),
    (VALID.split(b"\r\n\r\n", 1)[0], "text/csv"),
    (VALID, "text/html"),
    (VALID, None),
])
def test_invalid_artifact_retained_with_durable_failure_and_failed_replay(session, database, content, content_type):
    source = client(content)
    response = source.get_daily_snapshot.return_value
    source.get_daily_snapshot.return_value = DailySnapshotResponse(
        report_uri=response.report_uri, report_metadata=response.report_metadata,
        content=content, content_type=content_type, requested_api_version="1", used_api_version="1",
    )
    with pytest.raises(IntegrationExecutionError) as failure:
        DailySnapshotAcquisition(source).run(session)
    assert failure.value.failure_recorded and failure.value.stage == "extraction"
    with Session(database) as observer:
        artifact = observer.scalar(select(AcquiredArtifact))
        artifact_id = artifact.id
        assert artifact.artifact_bytes == content
        assert artifact.sha256 == hashlib.sha256(content).hexdigest()
        assert artifact.content_length == len(content)
        assert artifact.report_metadata["report"] == {"id": "daily"}
        run = observer.get(ProcessingRun, failure.value.processing_run_id)
        assert run.failure_code == "parse_error" and run.failure_message and run.completed_at
        assert run.parser_version == "daily-snapshot-parser-2"
        assert counts(observer)["staging_rows"] == counts(observer)["staging_datasets"] == 0
    source.get_daily_snapshot.side_effect = AssertionError("No reacquisition")
    with pytest.raises(IntegrationExecutionError) as replay_failure:
        replay_daily_snapshot(session, artifact_id)
    assert replay_failure.value.failure_recorded and replay_failure.value.stage == "extraction"
    assert source.get_daily_snapshot.call_count == 1
    with Session(database) as observer:
        runs = observer.scalars(select(ProcessingRun)).all()
        assert len(runs) == 2 and all(run.status == "failed" for run in runs)
        assert counts(observer)["staging_rows"] == counts(observer)["staging_datasets"] == 0
        assert observer.get(AcquiredArtifact, artifact_id).artifact_bytes == content


def test_synthetic_csv_values_survive_acquisition_staging_and_replay(session, database):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    values = [' ä ö ü Ä Ö Ü é è à ç Ελληνικά \u00a0 \u200b Â® Ã¶ ',
              'comma, "quoted"\nLF\r\nCRLF\r\n\r\nblank']
    writer.writerows([
        ["Report Type", "Report Name", "Date Requested (UTC)"],
        ["Daily Snapshot", "Fictional", "2024-02-29T00:00:00Z"], [],
        ["First"], ["B", "A"], ["1", values[0]], ["2", values[1]], [],
        ["Empty"], ["Header"], [], ["Last"], ["__extra__"], ["source value"],
    ])
    content = stream.getvalue().encode("utf-8")
    source = client(content)
    DailySnapshotAcquisition(source).run(session)
    with Session(database) as observer:
        artifact_id = observer.scalar(select(AcquiredArtifact.id))
    replay_daily_snapshot(session, artifact_id)
    assert source.get_daily_snapshot.call_count == 1
    with Session(database) as observer:
        artifact = observer.get(AcquiredArtifact, artifact_id)
        assert artifact.artifact_bytes == content
        assert artifact.sha256 == hashlib.sha256(content).hexdigest()
        datasets = observer.scalars(select(StagingDataset).order_by(StagingDataset.id)).all()
        assert [(d.source_dataset_name, d.section_order, d.row_count) for d in datasets] == [
            ("First", 1, 2), ("Empty", 2, 0), ("Last", 3, 1),
        ]
        assert datasets[0].source_headers == ["B", "A"]
        rows = observer.scalars(select(StagingRow).order_by(StagingRow.id)).all()
        assert [row.raw_row_json for row in rows] == [
            {"B": "1", "A": values[0]}, {"B": "2", "A": values[1]}, {"__extra__": "source value"},
        ]
        assert [row.source_row_number for row in rows] == [1, 2, 1]


def test_metadata_is_ordered_complete_and_separate_on_replay(session, database, monkeypatch):
    from dataclasses import replace

    expected = {
        "Report Type": "Daily Snapshot", "Report Name": "  é Ελληνικά Â® Ã¶ \u00a0\u200b  ",
        "Date Requested (UTC)": "2024-02-29T00:00:00Z", "Unknown Column": " unchanged ",
    }
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerows([list(expected), list(expected.values()), [], ["Synthetic"], ["Value"], ["a"]])
    source = client(stream.getvalue().encode("utf-8"))
    DailySnapshotAcquisition(source).run(session)
    with Session(database) as observer:
        artifact = observer.scalar(select(AcquiredArtifact))
        artifact_id = artifact.id
        run = observer.scalar(select(ProcessingRun))
        assert list(run.file_metadata.items()) == list(expected.items())
        assert artifact.report_metadata["report"] == {"id": "daily"}
        # The database stores ordered pairs, not an order-losing JSON object.
        raw = observer.execute(text("SELECT file_metadata FROM processing_runs")).scalar_one()
        assert json.loads(raw) == [list(item) for item in expected.items()]

    replay_metadata = {**expected, "Parser addition": "replay only"}
    monkeypatch.setattr(processing, "parse_daily_snapshot", lambda data: replace(
        parse_daily_snapshot(data), file_metadata=replay_metadata,
    ))
    replay_daily_snapshot(session, artifact_id, parser_version="synthetic-next")
    assert source.get_daily_snapshot.call_count == 1
    with Session(database) as observer:
        runs = observer.scalars(select(ProcessingRun).order_by(ProcessingRun.id)).all()
        assert list(runs[0].file_metadata.items()) == list(expected.items())
        assert list(runs[1].file_metadata.items()) == list(replay_metadata.items())


def test_metadata_survives_later_staging_failure(session, database, monkeypatch):
    original = processing.stage_daily_snapshot

    def fail_after_staging(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError(SENSITIVE)

    monkeypatch.setattr(processing, "stage_daily_snapshot", fail_after_staging)
    with pytest.raises(IntegrationExecutionError) as failure:
        DailySnapshotAcquisition(client()).run(session)
    assert failure.value.failure_recorded and failure.value.stage == "staging"
    with Session(database) as observer:
        run = observer.get(ProcessingRun, failure.value.processing_run_id)
        assert run.status == "failed"
        assert run.file_metadata == parse_daily_snapshot(VALID).file_metadata
        assert counts(observer)["staging_rows"] == counts(observer)["staging_datasets"] == 0


def test_metadata_is_sql_null_before_successful_parse(session, database):
    with pytest.raises(IntegrationExecutionError) as failure:
        DailySnapshotAcquisition(client(b"invalid")).run(session)
    with Session(database) as observer:
        assert observer.get(ProcessingRun, failure.value.processing_run_id).file_metadata is None
        assert observer.execute(text(
            "SELECT COUNT(*) FROM processing_runs WHERE file_metadata IS NULL"
        )).scalar_one() == 1


def test_changed_snapshot_content_has_one_new_result_and_then_reuses_it(session, database):
    first = DailySnapshotAcquisition(client()).run(session)
    changed = client(VALID.replace(b'"001"', b'"003"'))
    DailySnapshotAcquisition(changed).run(session)
    DailySnapshotAcquisition(changed).run(session)
    with Session(database) as observer:
        runs = observer.scalars(select(ProcessingRun).order_by(ProcessingRun.id)).all()
        assert first.id is not None
        assert [r.reused_from_run_id for r in runs] == [None, None, runs[1].id]
        assert counts(observer)['artifact_contents'] == 2
        assert counts(observer)['staging_rows'] == 4


def test_same_bytes_with_new_parser_are_a_distinct_interpretation(session, database):
    DailySnapshotAcquisition(client()).run(session)
    with Session(database) as observer:
        artifact_id = observer.scalar(select(AcquiredArtifact.id))
    next_run = replay_daily_snapshot(session, artifact_id, parser_version='explicit-new-interpretation')
    assert next_run.reused_from_run_id is None
    repeated = replay_daily_snapshot(session, artifact_id, parser_version='explicit-new-interpretation')
    assert repeated.reused_from_run_id == next_run.id
    with Session(database) as observer:
        assert counts(observer)['staging_rows'] == 4
