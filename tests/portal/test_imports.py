from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.core.db.models import ImportExecution, ImportMutex, ImportSchedule
from app.domain.models import ManualImportRequest
from app.integration.scheduler.control import QUEUE_LOCK
from app.integration.scheduler.service import ImportScheduler
from app.portal.import_queries import window_coverage
from app.portal.import_routes import router


@pytest.fixture
def imports_portal(portal, monkeypatch):
    client, factory = portal
    client.app.include_router(router)
    monkeypatch.setattr("app.portal.import_routes.SessionFactory", factory)
    with factory() as s:
        s.add(ImportMutex(import_key=QUEUE_LOCK))
        s.commit()
    scheduler = ImportScheduler(
        factory,
        {
            "sai": lambda: None,
            "daily_snapshot": lambda: None,
            "exceptions": lambda: None,
            "user_activity": lambda: None,
        },
    )
    for key in scheduler.handlers:
        scheduler.configure(key, enabled=False)
    return client, factory


def test_read_only_overview_and_same_origin_controls(imports_portal):
    client, factory = imports_portal
    response = client.get("/imports")
    assert (
        response.status_code == 200 and "No recent scheduler heartbeat" in response.text
    )
    assert '<html lang="en">' in response.text and "Backfill" in response.text
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(ManualImportRequest)) == 0
        assert s.scalar(select(func.count()).select_from(ImportExecution)) == 0
    assert client.post("/imports/sai/run").status_code == 403
    assert (
        client.post(
            "/imports/sai/run", headers={"Origin": "http://evil.test"}
        ).status_code
        == 403
    )
    for _ in range(2):
        assert (
            client.post(
                "/imports/sai/run", headers={"Origin": "http://testserver"}
            ).status_code
            == 200
        )
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(ManualImportRequest)) == 1
    assert client.get("/imports?source=unknown").status_code == 404
    assert (
        "<script>oops</script>"
        not in client.get("/imports?notice=<script>oops</script>").text
    )


def test_cadence_save_preserves_pause_and_resume_is_explicit(imports_portal):
    client, factory = imports_portal
    headers = {"Origin": "http://testserver"}
    result = client.post(
        "/imports/sai/configure",
        headers=headers,
        data={"mode": "interval", "hours": "2"},
    )
    assert result.status_code == 200 and "Cadence saved" in result.text
    with factory() as s:
        schedule = s.scalar(
            select(ImportSchedule).where(ImportSchedule.import_key == "sai")
        )
        assert not schedule.enabled and schedule.interval_seconds == 7200
    client.post("/imports/sai/resume", headers=headers)
    with factory() as s:
        assert s.scalar(
            select(ImportSchedule).where(ImportSchedule.import_key == "sai")
        ).enabled
    client.post("/imports/sai/pause", headers=headers)
    assert (
        client.post(
            "/imports/sai/configure",
            headers=headers,
            data={"mode": "daily", "daily_time": "25:00"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/imports/sai/configure",
            headers=headers,
            data={"mode": "interval", "hours": "0"},
        ).status_code
        == 422
    )
    with factory() as s:
        assert not s.scalar(
            select(ImportSchedule).where(ImportSchedule.import_key == "sai")
        ).enabled


def test_backfill_validation_and_cancel_do_not_modify_schedule(imports_portal):
    client, factory = imports_portal
    headers = {"Origin": "http://testserver"}
    with factory() as s:
        before = s.scalar(
            select(ImportSchedule.next_run_at).where(
                ImportSchedule.import_key == "exceptions"
            )
        )
    result = client.post(
        "/imports/exceptions/backfill",
        headers=headers,
        data={"start": "2026-08-01", "end": "2026-08-31"},
    )
    assert result.status_code == 200 and "2026-08-01" in result.text
    with factory() as s:
        request = s.scalar(select(ManualImportRequest))
        identifier = request.id
        assert request.kind == "backfill" and request.start_date == date(2026, 8, 1)
        assert (
            s.scalar(
                select(ImportSchedule.next_run_at).where(
                    ImportSchedule.import_key == "exceptions"
                )
            )
            == before
        )
    assert (
        client.post(
            f"/imports/requests/{identifier}/cancel", headers=headers
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/imports/sai/backfill",
            headers=headers,
            data={"start": "2026-08-01", "end": "2026-08-01"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/imports/user_activity/backfill",
            headers=headers,
            data={"start": "2999-01-01", "end": "2999-01-01"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/imports/exceptions/backfill",
            headers=headers,
            data={"start": "2026-08-01", "end": "2026-09-30"},
        ).status_code
        == 422
    )


def test_complete_day_coverage_merges_overlaps_and_keeps_gaps():
    from datetime import datetime

    a = datetime.fromisoformat("2026-08-01T12:00:00")
    windows = [
        (a, a + timedelta(days=2)),
        (a + timedelta(days=1), a + timedelta(days=3)),
        (a + timedelta(days=5), a + timedelta(days=6)),
    ]
    # The first partial day and the uncovered middle days must not count as full coverage.
    assert "2/6 complete UTC days" in window_coverage(windows, a + timedelta(days=10))
