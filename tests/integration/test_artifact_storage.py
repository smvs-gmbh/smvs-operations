from dataclasses import replace

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.core.db.models import AcquiredArtifact, ArtifactContent, Base, IntegrationJob
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow
from app.integration.sources.nmvs.reporting import DailySnapshotResponse


@pytest.fixture
def session():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def job(session):
    value = IntegrationJob(
        source_name="NMVS", channel_name="Reporting API", report_type="DailySnapshot",
        status="acquiring", created_at=utcnow(),
    )
    session.add(value)
    session.flush()
    return value


def response(data=b"unchanged bytes"):
    return DailySnapshotResponse(
        report_uri="/reports/first", report_metadata={"id": "first"}, content=data,
        content_type="text/csv", requested_api_version="1", used_api_version="1",
    )


def test_duplicate_bytes_preserve_each_job_and_acquisition_metadata(session):
    store = MySQLArtifactStore()
    first_job = job(session)
    first = store.save_daily_snapshot(session, first_job, response())
    session.commit()
    second_job = job(session)
    second = store.save_daily_snapshot(session, second_job, replace(
        response(), report_uri="/reports/second", report_metadata={"id": "second"}, used_api_version="2",
    ))
    session.commit()
    assert first.id != second.id
    assert first.content_id == second.content_id
    assert first.integration_job_id == first_job.id
    assert second.integration_job_id == second_job.id
    assert first.source_uri == "/reports/first"
    assert second.source_uri == "/reports/second"
    assert first.report_metadata["used_api_version"] == "1"
    assert second.report_metadata["used_api_version"] == "2"
    assert second.report_metadata["report"] == {"id": "second"}
    assert first.received_at is not None and second.received_at is not None
    assert session.scalar(select(func.count()).select_from(ArtifactContent)) == 1
    assert len(session.scalars(select(AcquiredArtifact)).all()) == 2


def test_different_bytes_are_distinct_content(session):
    store = MySQLArtifactStore()
    first = store.save_daily_snapshot(session, job(session), response(b"one"))
    second = store.save_daily_snapshot(session, job(session), response(b"two"))
    session.commit()
    assert first.content_id != second.content_id
    assert first.artifact_bytes == b"one"
    assert second.artifact_bytes == b"two"


def test_duplicate_insert_race_recovery_does_not_rollback_acquisition(session, monkeypatch):
    store = MySQLArtifactStore()
    first = store.save_daily_snapshot(session, job(session), response())
    session.commit()
    second_job = job(session)
    original_scalar = session.scalar
    reads = []

    def stale_first_read(statement, *args, **kwargs):
        reads.append(statement)
        if len(reads) == 1:
            return None  # Simulate a winner committing after the initial lookup.
        return original_scalar(statement, *args, **kwargs)

    monkeypatch.setattr(session, "scalar", stale_first_read)
    second = store.save_daily_snapshot(session, second_job, response())
    session.commit()
    assert first.content_id == second.content_id
    assert first.id != second.id
    assert session.get(IntegrationJob, second_job.id) is not None
    assert reads[1]._for_update_arg is not None


def test_checksum_match_with_different_bytes_is_rejected(session):
    store = MySQLArtifactStore()
    first = store.save_daily_snapshot(session, job(session), response())
    session.commit()
    first.content.artifact_bytes = b"corrupt"
    session.commit()
    with pytest.raises(ValueError, match="integrity failure"):
        store.save_daily_snapshot(session, job(session), response())
    session.rollback()
    assert session.scalar(select(func.count()).select_from(AcquiredArtifact)) == 1
