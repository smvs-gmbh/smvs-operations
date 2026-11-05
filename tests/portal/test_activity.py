import pytest
from sqlalchemy import select

from app.core.db.models import ImportMutex
from app.domain.activity.mapping import MUTEX, publish_activity
from app.domain.models import ActivityFact
from app.portal.activity_routes import router
from tests.integration.activity.test_activity import NS, acquire, workbook


@pytest.fixture
def activity_portal(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory() as s:
        s.add(ImportMutex(import_key=MUTEX))
        s.commit()
    return client, factory


def test_empty_state_and_date_validation(activity_portal):
    client, _ = activity_portal
    response = client.get("/activity/verification")
    assert response.status_code == 200 and "No activity data" in response.text
    assert client.get("/activity/unknown").status_code == 404
    for suffix in [
        "?start=2026-08-03&end=2026-08-01",
        "?start=2024-01-01&end=2026-08-01",
        "?sort=sql",
        "?end=2999-01-01",
        "?market=DE",
    ]:
        assert client.get("/activity/verification" + suffix).status_code == 422


def test_totals_bulk_units_and_gaps_are_distinct(activity_portal):
    client, factory = activity_portal
    publish_activity(factory, acquire(factory, workbook(extra=True)), NS)
    page = client.get("/activity/verification?start=2026-08-01&end=2026-08-03")
    assert page.status_code == 200
    assert (
        "Data gaps" in page.text
        and "27.500" in page.text
        and "Pack metrics" in page.text
    )
    assert "<strong>12</strong>" in page.text and "<strong>2</strong>" in page.text
    assert "No data imported" in page.text and "2026-08-02: 0 Transactions" in page.text
    assert "16.67 %" in page.text
    assert "<strong>67</strong>" not in page.text
    assert (
        client.get("/activity/imt?start=2026-08-01&end=2026-08-02").status_code == 200
    )


def test_filters_drilldown_sort_and_safe_labels(activity_portal):
    client, factory = activity_portal
    publish_activity(factory, acquire(factory, workbook()), NS)
    with factory() as s:
        r = s.scalar(select(ActivityFact).where(ActivityFact.section == "Verification"))
        r.organisation_name = "<script>danger</script>"
        s.commit()
    text = client.get(
        "/activity/verification?start=2026-08-01&end=2026-08-02&sort=exceptions"
    ).text
    assert (
        "&lt;script&gt;danger&lt;/script&gt;" in text
        and "<script>danger</script>" not in text
    )
    filtered = client.get(
        "/activity/verification?start=2026-08-01&end=2026-08-02&organisation=05"
    )
    assert filtered.status_code == 200 and "Single Pack Verification" in filtered.text
    none = client.get(
        "/activity/verification?start=2026-08-01&end=2026-08-02&organisation=missing"
    ).text
    assert "<strong>0</strong>" in none and "No activity" in none
    day = client.get(
        "/activity/verification?start=2026-08-01&end=2026-08-02&day=2026-08-02"
    ).text
    assert "Daily details 2026-08-02" in day and "Show full period" in day


def test_previous_only_organisation_exposes_stopped_activity(activity_portal):
    from datetime import date

    from app.portal.activity_queries import activity

    _client, factory = activity_portal
    publish_activity(factory, acquire(factory, workbook()), NS)
    with factory() as s:
        result = activity(
            s, section="Verification", start=date(2026, 8, 2), end=date(2026, 8, 2)
        )
        assert result["comparison"] == -100.0
        assert result["rows"][0]["count"] == 0 and result["rows"][0]["delta"] == -100.0
