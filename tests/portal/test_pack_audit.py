import pytest

from app.core.db.models import ImportMutex
from app.domain.exceptions.mapping import MUTEX, publish_exceptions
from app.domain.pack_audit import service
from app.portal.pack_audit_routes import router
from tests.integration.exceptions.test_exceptions import NS, acquire, alert, page
from tests.integration.pack_audit.test_pack_audit import PARAMS, content


@pytest.fixture
def pack_portal(portal, monkeypatch):
    client, factory = portal
    client.app.include_router(router)
    with factory() as s:
        for name in (service.QUEUE_LOCK, service.WORKER_LOCK, MUTEX):
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
    assert response.status_code == 200 and "Queued" in response.text


def test_real_schematic_and_originals_and_missing_match(pack_portal):
    client, factory = pack_portal
    with factory() as s:
        run_id = service.retain(
            s, content(), "https://example.test/report/reports/one", {"request": PARAMS}
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
    result = client.get("/exceptions/1/audit-trail")
    assert result.status_code == 200
    assert "Pack history at a glance" in result.text and "This exception" in result.text
    assert "Active → Exported" in result.text and "unchanged" in result.text
    assert "4 audit entries · 3 transactions" in result.text
    assert "Show 2 original events" in result.text and "Before the error" in result.text
    assert "no root cause finding" in result.text
    assert client.get("/exceptions/1/audit-trail?show=all").status_code == 200
    assert client.get("/exceptions/999/audit-trail").status_code == 404
    original = client.get(f"/pack-audit/reports/{report_id}/original")
    assert original.status_code == 200 and original.content == content()
    assert client.get("/pack-audit/reports/999/original").status_code == 404
