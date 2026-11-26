from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.db.models import ImportMutex
from app.domain.exceptions.mapping import MUTEX, publish_exceptions
from app.domain.models import LocalLocation
from app.domain.pack_audit import service
from app.domain.participants.mapping import MUTEX as PARTICIPANT_MUTEX
from app.domain.participants.mapping import publish_participants
from app.portal.pack_audit_routes import router
from tests.domain.test_participants import source
from tests.integration.exceptions.test_exceptions import NS, acquire, alert, page
from tests.integration.pack_audit.test_pack_audit import PARAMS, content, events


@pytest.fixture
def pack_portal(portal, monkeypatch):
    client, factory = portal
    client.app.include_router(router)
    with factory() as s:
        for name in (service.QUEUE_LOCK, service.WORKER_LOCK, MUTEX, PARTICIPANT_MUTEX):
            s.add(ImportMutex(import_key=name))
        s.commit()
    monkeypatch.setattr("app.portal.pack_audit_routes.SessionFactory", factory)
    publish_exceptions(factory, acquire(factory, [page([alert()])]), NS)
    return client, factory


def test_get_never_queues_and_post_requires_explicit_origin(pack_portal):
    client, _ = pack_portal
    text = client.get("/exceptions/1/audit-trail").text
    assert "No report loaded" in text and "Load pack audit trail" in text
    assert client.post("/exceptions/1/audit-trail").status_code == 403
    assert (
        client.post(
            "/exceptions/1/audit-trail", headers={"Origin": "http://evil.test"}
        ).status_code
        == 403
    )
    response = client.post(
        "/exceptions/1/audit-trail", headers={"Origin": "http://testserver"}
    )
    assert response.status_code == 200 and "Waiting for background worker" in response.text


def test_real_schematic_and_originals_and_missing_match(pack_portal):
    client, factory = pack_portal
    rows = events()
    rows[0]["Event Details"] += " Location: L-1;"
    rows[2]["Event Details"] += " Location: Unknown-location;"
    csv = content(rows)
    with factory() as s:
        run_id = service.retain(
            s, csv, "https://example.test/report/reports/one", {"request": PARAMS}
        )
        report = service.publish(s, run_id, NS, PARAMS)
        s.commit()
        report_id = report.id
    task = service.request_report(factory, 1)
    from app.domain.models import PackAuditRequest

    with factory() as s:
        task = s.get(PackAuditRequest, task.id)
        task.status = "ready"
        task.latest_report_id = report_id
        s.commit()
    assert (
        "Request from CH · Location L-1" in client.get("/exceptions/1/audit-trail").text
    )
    publish_participants(
        factory,
        source(
            factory,
            locs=[
                {
                    "Organisation Id": "Org-001",
                    "Location Id": "L-1",
                    "Location Name": "Apotheke Zürich",
                }
            ],
        ),
        NS,
    )
    with factory() as s:
        location_id = s.scalar(select(LocalLocation.id))
    result = client.get("/exceptions/1/audit-trail")
    assert result.status_code == 200
    assert "Pack history at a glance" in result.text and "This exception" in result.text
    assert "Active → Exported" in result.text and "unchanged" in result.text
    assert "4 audit entries · 3 transactions" in result.text
    assert "Show 2 original events" in result.text and "Before the error" in result.text
    assert "no root cause finding" in result.text
    assert f'href="/locations/{location_id}">Apotheke Zürich →' in result.text
    assert "Request from EU · Location L-1" in result.text
    assert "Request from CH · Location Unknown-location" in result.text
    assert client.get("/exceptions/1/audit-trail?show=all").status_code == 200
    assert client.get("/exceptions/999/audit-trail").status_code == 404
    original = client.get(f"/pack-audit/reports/{report_id}/original")
    assert original.status_code == 200 and original.content == csv
    assert client.get("/pack-audit/reports/999/original").status_code == 404


@pytest.mark.parametrize("worker_mode,age,expected", [
    (None, 0, False), ("stopped", 0, False), ("manual", 61, False),
    ("running", 60, True), ("manual", 15, True), ("running", -3600, False),
])
def test_request_reports_worker_liveness_without_losing_queued_work(
    pack_portal, monkeypatch, worker_mode, age, expected
):
    from sqlalchemy import func

    from app.domain.models import PackAuditRequest, SchedulerHeartbeat

    client, factory = pack_portal
    now = datetime(2026, 11, 26, 10, 0, tzinfo=UTC).replace(tzinfo=None)
    monkeypatch.setattr("app.portal.worker_status.utcnow", lambda: now)
    monkeypatch.setattr("app.domain.pack_audit.service.utcnow", lambda: now)
    if worker_mode:
        with factory.begin() as session:
            session.add(SchedulerHeartbeat(worker_id="test-worker", started_at=now-timedelta(days=1),
                                           last_seen_at=now-timedelta(seconds=age), status=worker_mode))
    initial = client.get("/exceptions/1/audit-trail")
    assert initial.status_code == 200 and "Load pack audit trail" in initial.text
    assert ("Background worker connected" in initial.text) is expected
    assert "View background-worker status →" in initial.text
    if not worker_mode:
        assert "No worker heartbeat has been recorded." in initial.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PackAuditRequest)) == 0
    for _ in range(2):
        result = client.post("/exceptions/1/audit-trail", headers={"Origin": "http://testserver"})
        assert result.status_code == 200
        assert ("Queued · worker available" if expected else "Waiting for background worker") in result.text
        assert "Attempts: 0" in result.text
        assert "window.location.reload()" in result.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PackAuditRequest)) == 1
        task = session.scalar(select(PackAuditRequest))
        assert task.status == "queued" and task.attempt_count == 0


def test_worker_recovery_running_and_retry_states_are_visible(pack_portal, monkeypatch):
    from app.domain.models import PackAuditRequest, SchedulerHeartbeat

    client, factory = pack_portal
    now = datetime(2026, 11, 26, 10, 0, tzinfo=UTC).replace(tzinfo=None)
    monkeypatch.setattr("app.portal.worker_status.utcnow", lambda: now)
    monkeypatch.setattr("app.domain.pack_audit.service.utcnow", lambda: now)
    task = service.request_report(factory, 1)
    assert "Waiting for background worker" in client.get("/exceptions/1/audit-trail").text
    with factory.begin() as session:
        session.add(SchedulerHeartbeat(worker_id="live", started_at=now, last_seen_at=now, status="manual"))
        # A more recent stopped worker must not hide another live worker.
        session.add(SchedulerHeartbeat(worker_id="stopped", started_at=now, last_seen_at=now, status="stopped"))
    assert "Queued · worker available" in client.get("/exceptions/1/audit-trail").text
    with factory.begin() as session:
        queued = session.get(PackAuditRequest, task.id)
        queued.retry_at = now + timedelta(minutes=5)
        queued.attempt_count = 1
    response = client.get("/exceptions/1/audit-trail")
    assert "Retry scheduled" in response.text and "2026-11-26 10:05:00 UTC" in response.text
    with factory.begin() as session:
        session.get(PackAuditRequest, task.id).status = "running"
    assert "Retrieving report …" in client.get("/exceptions/1/audit-trail").text
    monkeypatch.setattr("app.portal.worker_status.utcnow", lambda: now + timedelta(seconds=61))
    assert "Processing status not confirmed" in client.get("/exceptions/1/audit-trail").text
    with factory() as session:
        assert session.get(PackAuditRequest, task.id).status == "running"


def test_report_waiting_behind_import_is_identified(pack_portal, monkeypatch):
    from app.core.db.models import ImportExecution
    from app.domain.models import SchedulerHeartbeat
    from app.integration.scheduler.service import ImportScheduler

    client, factory = pack_portal
    now = datetime(2026, 11, 26, 10, 0, tzinfo=UTC).replace(tzinfo=None)
    monkeypatch.setattr("app.portal.worker_status.utcnow", lambda: now)
    monkeypatch.setattr("app.domain.pack_audit.service.utcnow", lambda: now)
    schedule = ImportScheduler(factory, {"test-import": lambda: None}).configure("test-import")
    with factory.begin() as session:
        session.add(SchedulerHeartbeat(worker_id="live", started_at=now, last_seen_at=now, status="running"))
        execution = ImportExecution(schedule_id=schedule, trigger="manual", status="running", started_at=now)
        session.add(execution)
        session.flush()
        execution_id = execution.id
    service.request_report(factory, 1)
    response = client.get("/exceptions/1/audit-trail")
    assert "Queued behind background work" in response.text
    with factory.begin() as session:
        execution = session.get(ImportExecution, execution_id)
        execution.status = "succeeded"
        execution.completed_at = now
    assert "Queued · worker available" in client.get("/exceptions/1/audit-trail").text


def test_fresh_heartbeat_does_not_hide_stalled_queue(pack_portal, monkeypatch):
    from app.domain.models import PackAuditRequest, SchedulerHeartbeat

    client, factory = pack_portal
    now = datetime(2026, 11, 26, 10, 0, tzinfo=UTC).replace(tzinfo=None)
    monkeypatch.setattr('app.portal.worker_status.utcnow', lambda: now)
    monkeypatch.setattr('app.domain.pack_audit.service.utcnow', lambda: now)
    task = service.request_report(factory, 1)
    with factory.begin() as session:
        session.get(PackAuditRequest, task.id).requested_at = now-timedelta(minutes=3)
        session.add(SchedulerHeartbeat(worker_id='live', started_at=now-timedelta(hours=1),
                                       last_seen_at=now, status='manual'))
    assert 'Queue pickup delayed' in client.get('/exceptions/1/audit-trail').text
    with factory.begin() as session:
        session.get(SchedulerHeartbeat, 'live').started_at = now
    assert 'Queued · worker available' in client.get('/exceptions/1/audit-trail').text
