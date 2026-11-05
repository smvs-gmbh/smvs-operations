import pytest
from sqlalchemy import func, select

from app.core.db.models import ImportMutex
from app.domain.exceptions.mapping import MUTEX, publish_exceptions
from app.domain.models import UploadRequest
from app.domain.uploads import service
from app.portal.upload_routes import router
from tests.integration.exceptions.test_exceptions import NS, acquire, alert, page
from tests.integration.uploads.test_uploads import END, START, content


@pytest.fixture
def upload_portal(portal, monkeypatch):
    client, factory = portal
    client.app.include_router(router)
    monkeypatch.setattr("app.portal.upload_routes.SessionFactory", factory)
    with factory() as s:
        s.add_all(
            [
                ImportMutex(import_key=name)
                for name in (MUTEX, service.QUEUE_LOCK, service.WORKER_LOCK)
            ]
        )
        s.commit()
    publish_exceptions(factory, acquire(factory, [page([alert()])]), NS)
    return client, factory


def test_read_only_view_missing_coverage_and_explicit_queue(upload_portal):
    client, factory = upload_portal
    url = "/exceptions/1/uploads?start=2026-10-01&end=2026-10-02"
    response = client.get(url)
    assert response.status_code == 200 and "not fully checked yet" in response.text
    with factory() as s:
        assert not s.scalar(select(func.count()).select_from(UploadRequest))
    assert client.post(url).status_code == 403
    assert client.post(url, headers={"Origin": "http://evil.test"}).status_code == 403
    response = client.post(url, headers={"Origin": "http://testserver"})
    assert response.status_code == 200 and "Queued" in response.text
    client.post(url, headers={"Origin": "http://testserver"})
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(UploadRequest)) == 1
    assert (
        client.get("/exceptions/1/uploads?start=2026-09-01&end=2026-10-31").status_code
        == 422
    )
    assert client.get("/exceptions/999/uploads").status_code == 404


def test_matching_upload_coverage_original_and_no_unnecessary_queue(upload_portal):
    client, factory = upload_portal
    with factory() as s:
        run = service.retain(
            s,
            content(),
            None,
            {
                "source_namespace": NS,
                "request": {
                    "startDateTime": START.isoformat() + "Z",
                    "endDateTime": END.isoformat() + "Z",
                },
            },
            provided=True,
        )
        report = service.publish(s, run, NS)
        s.commit()
        report_id = report.id
    url = "/exceptions/1/uploads?start=2026-10-01&end=2026-10-02"
    result = client.get(url)
    assert result.status_code == 200 and "Matching upload events found" in result.text
    assert (
        "Stored" in result.text
        and "does not confirm" in result.text
        and "individual serial number" in result.text
    )
    assert "Upload processed" in result.text and "Successful" in result.text
    client.post(url, headers={"Origin": "http://testserver"})
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(UploadRequest)) == 0
    assert client.get(f"/upload-reports/{report_id}/original").content == content()
    assert client.get("/upload-reports/999/original").status_code == 404


def test_historic_matches_reuse_local_reports_without_changing_coverage(upload_portal):
    import html
    import re

    from app.integration.sources.nmvs.uploads.parsing import parse_upload

    client, factory = upload_portal
    old = content().replace(b"2026-10-", b"2026-01-")
    # Overlapping report versions, a foreign source, wrong product and wrong-case
    # batch must not create duplicate or unrelated historical suggestions.
    for data, namespace in [
        (old, NS),
        (old.replace(b"Upload test", b"Another title"), NS),
        (
            old.replace(b"Upload test", b"Another source").replace(
                b"2026-01-02T11:00:00Z", b"2026-01-01T11:00:00Z"
            ),
            "another-source",
        ),
        (old.replace(b"Lot-001", b"LOT-001"), NS),
        (old.replace(b"04006381333931", b"07680548790415"), NS),
    ]:
        meta = parse_upload(data).file_metadata
        with factory() as s:
            run = service.retain(
                s,
                data,
                None,
                {
                    "source_namespace": namespace,
                    "request": {
                        "startDateTime": meta["Start Date & Time (UTC)"],
                        "endDateTime": meta["End Date & Time (UTC)"],
                    },
                },
                provided=True,
            )
            service.publish(s, run, namespace)
            s.commit()
    response = client.get("/exceptions/1/uploads?start=2026-10-04&end=2026-10-04")
    assert response.status_code == 200
    assert (
        "Accepted reports are still missing for parts of this period" in response.text
    )
    assert "1 match found outside this period" in response.text
    assert "Matching batch events are already available on 2026-01-02" in response.text
    assert "Suggested gap:" not in response.text
    assert "2026-01-02" in response.text and "Stored" in response.text
    link = re.search(r'href="([^"]+)"[^>]*>View this day', response.text)
    assert link is not None
    day = client.get(html.unescape(link[1]))
    assert day.status_code == 200
    assert "Matching upload events found" in day.text and "Upload processed" in day.text
    assert "1 matching event in the selected period" in day.text
    assert "Period fully covered by accepted reports" in day.text
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(UploadRequest)) == 0


@pytest.mark.parametrize(
    "batch, anchored", [("Lot-001", True), ("LOT-001", False), ("BAD", False)]
)
def test_creation_anchor_requires_the_matched_pack_and_exact_stored_batch(
    upload_portal, batch, anchored
):
    from app.domain.models import PackAuditRequest
    from app.domain.pack_audit import service as pack_service
    from tests.integration.pack_audit.test_pack_audit import PARAMS, event
    from tests.integration.pack_audit.test_pack_audit import content as audit_content

    client, factory = upload_portal
    creation = event("PpdNewPackCreated", "tx-create", "2026-07-16T10:00:00Z")
    creation["Batch Number"] = batch
    with factory() as s:
        s.add(ImportMutex(import_key=pack_service.QUEUE_LOCK))
        run = pack_service.retain(
            s,
            audit_content(rows=[creation]),
            "https://example.test/report/reports/one",
            {"request": PARAMS},
        )
        report = pack_service.publish(s, run, NS, PARAMS)
        s.commit()
        report_id = report.id
    task = pack_service.request_report(factory, 1)
    with factory() as s:
        item = s.get(PackAuditRequest, task.id)
        item.status = "ready"
        item.latest_report_id = report_id
        s.commit()
    result = client.get("/exceptions/1/uploads")
    assert result.status_code == 200
    if anchored:
        assert "Pack creation recorded:" in result.text
        assert "Suggested gap: 2026-07-15 to 2026-07-17" in result.text
        assert 'name="start" value="2026-07-15"' in result.text
        assert 'name="end" value="2026-07-17"' in result.text
        manual = client.get("/exceptions/1/uploads?start=2026-10-01&end=2026-10-02")
        assert 'name="start" value="2026-10-01"' in manual.text
    else:
        assert "No unambiguous pack creation date" in result.text
        assert 'name="start" value="2026-09-06"' in result.text
        assert 'name="end" value="2026-10-06"' in result.text
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(UploadRequest)) == 0


def test_suggested_gap_skips_covered_days_and_stays_bounded():
    from datetime import date, datetime
    from types import SimpleNamespace

    from app.portal.upload_routes import suggested_gap

    reports = [
        SimpleNamespace(
            period_start=datetime.fromisoformat("2026-09-01"),
            period_end=datetime.fromisoformat("2026-09-10"),
        )
    ]
    assert suggested_gap(reports, date(2026, 8, 1), date(2026, 9, 15)) == (
        date(2026, 9, 10),
        date(2026, 9, 15),
    )
    assert suggested_gap(reports, date(2026, 9, 1), date(2026, 9, 9)) is None
    assert suggested_gap([], date(2026, 8, 1), date(2026, 9, 15)) == (
        date(2026, 8, 16),
        date(2026, 9, 15),
    )
