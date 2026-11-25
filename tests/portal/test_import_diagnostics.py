# ruff: noqa: F811 -- imported pytest fixture
from datetime import datetime, timedelta

from sqlalchemy import event, select

from app.core.db.models import (
    AcquiredArtifact,
    ArtifactContent,
    ImportExecution,
    ImportSchedule,
    IntegrationJob,
    ProcessingRun,
)
from app.portal.import_diagnostics import execution_details
from tests.portal.test_imports import imports_portal  # noqa: F401

START = datetime(2026, 11, 25, 3, 10)  # noqa: DTZ001 - stored UTC


def seed_failure(factory, *, linked=False, extra_jobs=0, failed=False):
    with factory() as session:
        schedule = session.scalar(
            select(ImportSchedule).where(ImportSchedule.import_key == "sai")
        )
        job = IntegrationJob(
            source_name="Refdata SAI",
            channel_name="Public XML Export",
            report_type="SAIFullExport",
            status="failed" if failed else "artifact_acquired",
            created_at=START + timedelta(seconds=1),
            started_at=START + timedelta(seconds=1),
            failure_code="parse_error" if failed else None,
            failure_stage="extraction" if failed else None,
        )
        session.add(job)
        session.flush()
        artifact = AcquiredArtifact(
            integration_job_id=job.id,
            source_name=job.source_name,
            channel_name=job.channel_name,
            report_type=job.report_type,
            source_uri="https://private.test/?token=hidden-secret",
            content=ArtifactContent(
                sha256="f" * 64,
                content_length=13,
                artifact_bytes=b"hidden-secret",
                created_at=START,
            ),
            report_metadata={"secret": "hidden-secret"},
            received_at=START,
            processing_status="acquired",
            created_at=START,
        )
        session.add(artifact)
        session.flush()
        run = ProcessingRun(
            artifact_id=artifact.id,
            run_type="initial_extraction",
            parser_version="hidden-secret",
            transform_version="none",
            status="failed" if failed else "extracting",
            started_at=START + timedelta(seconds=2),
            failure_code="parse_error" if failed else None,
            failure_stage="extraction" if failed else None,
        )
        session.add(run)
        execution = ImportExecution(
            schedule_id=schedule.id,
            trigger="schedule",
            status="failed" if failed else "interrupted",
            started_at=START,
            completed_at=START + timedelta(seconds=13),
            integration_job_id=job.id if linked else None,
            failure_code="parse_error" if failed else "worker_interrupted",
            failure_message="The Daily Snapshot could not be parsed."
            if failed
            else "Previous worker stopped before recording completion; retry is idempotent.",
        )
        session.add(execution)
        for _ in range(extra_jobs):
            session.add(
                IntegrationJob(
                    source_name=job.source_name,
                    channel_name=job.channel_name,
                    report_type=job.report_type,
                    status="acquiring",
                    created_at=START + timedelta(seconds=3),
                )
            )
        session.commit()
        return execution.id


def test_interrupted_history_explains_uncertainty_and_last_recorded_processing(
    imports_portal,
):
    client, factory = imports_portal
    identifier = seed_failure(factory)
    statements = []

    def record_sql(_, __, sql, *args):
        statements.append(sql)

    engine = factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", record_sql)
    try:
        response = client.get("/imports?source=sai")
    finally:
        event.remove(engine, "before_cursor_execute", record_sql)
    assert response.status_code == 200
    html = response.text
    assert "<summary>Failure details</summary>" in html
    assert f"<dt>Execution ID</dt><dd>{identifier}</dd>" in html
    assert "Time until interruption detected" in html and "13 seconds" in html
    assert "The exact cause was not recorded." in html
    assert "Extraction started; completion not recorded" in html
    assert "not explicitly linked to this execution" in html
    assert "hidden-secret" not in html and "private.test" not in html
    assert not any("artifact_contents" in sql.lower() for sql in statements)
    assert "Failure details" not in client.get("/imports?source=daily_snapshot").text
    with factory() as session:
        assert session.get(ImportExecution, identifier).status == "interrupted"


def test_linked_failure_displays_stage_without_guessing_other_jobs(imports_portal):
    client, factory = imports_portal
    seed_failure(factory, linked=True, failed=True, extra_jobs=1)
    html = client.get("/imports").text
    assert "Source job explicitly linked to this execution." in html
    assert "Extracting source records" in html and "parse_error" in html
    assert "Review the retained source format" in html
    assert "Several source jobs" not in html
    assert "hidden-secret" not in html


def test_ambiguous_source_activity_is_not_assigned_to_an_execution(imports_portal):
    client, factory = imports_portal
    seed_failure(factory, extra_jobs=1)
    html = client.get("/imports").text
    assert "Several source jobs were recorded in this time window" in html
    assert "<dt>Source job ID</dt>" not in html
    assert "<dt>Processing run ID</dt>" not in html


def test_missing_diagnostics_remain_explicit_and_success_has_no_failure_control(
    imports_portal,
):
    client, factory = imports_portal
    identifier = seed_failure(factory)
    with factory() as session:
        execution = session.get(ImportExecution, identifier)
        # Source activity outside this execution's period must never be used.
        execution.started_at += timedelta(days=1)
        execution.completed_at += timedelta(days=1)
        execution.failure_code = None
        detail = execution_details(session, execution, "SAIFullExport")
        assert detail["note"] == "No linked source job was recorded."
        assert not detail["sections"]
        assert ("Failure code", "Not recorded") in detail["facts"]
        execution.status = "succeeded"
        execution.failure_message = None
        session.commit()
    assert "Failure details" not in client.get("/imports").text
