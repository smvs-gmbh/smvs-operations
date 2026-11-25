import json
from datetime import date

import pytest
from sqlalchemy import select

from app.core.db.models import (
    AcquiredArtifact,
    ImportMutex,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.domain.participants.mapping import MUTEX, publish_participants
from app.integration.artifacts.storage import utcnow
from app.integration.sources.nmvs.parsing import record_hash
from app.portal.api_access import HEADERS, SERVICES, router
from tests.domain.test_participants import source
from tests.portal.test_table_views import save, tables  # noqa: F401

AGENT = "Apache-HttpClient/4.5.5 (Java/17.0.12)"


def seed(factory, *, day=date(2026, 11, 25), count=48, omit=(), status="succeeded"):
    identifier = source(factory, day=day)
    with factory.begin() as session:
        run = session.get(ProcessingRun, identifier)
        run.status = status
        run.completed_at = utcnow()
        session.get(AcquiredArtifact, run.artifact_id).channel_name = "Reporting API"
        for i, name in enumerate(SERVICES):
            if name in omit:
                continue
            data = [
                {
                    "Organisation Name": "Synthetic Pharmacy"
                    if n % 2 == 0
                    else "Other organisation",
                    "Organisation Id": "Org-001" if n % 2 == 0 else "Org-002",
                    "Organisation Type": "Pharmacy",
                    "Location Id": "Loc-001",
                    "Client Id": f"000{n:02d}",
                    "User-Agent": AGENT if n % 2 == 0 else "Other/1.0",
                    "IP Address": "192.0.2.10" if n % 2 == 0 else "2001:db8::1",
                    "Last API Request": "2026-11-24T13:45:01.123Z",
                    **(
                        {}
                        if name.startswith("Authentication")
                        else {"API Version": "3.1", "Requested API Version": "3.1"}
                    ),
                }
                for n in range(count if i == 0 else (1 if i == 1 else 0))
            ]
            dataset = StagingDataset(
                processing_run_id=identifier,
                artifact_id=run.artifact_id,
                source_dataset_name=name,
                source_headers=list(data[0]) if data else HEADERS,
                section_order=10 + i,
                row_count=len(data),
                extraction_status="extracted",
                created_at=utcnow(),
            )
            session.add(dataset)
            session.flush()
            for n, row in enumerate(data, 1):
                session.add(
                    StagingRow(
                        staging_dataset_id=dataset.id,
                        source_row_number=n,
                        source_record_hash=record_hash(row),
                        raw_row_json=row,
                        created_at=utcnow(),
                    )
                )
    return identifier


@pytest.fixture
def access(tables):  # noqa: F811 -- imported pytest fixture
    client, factory = tables
    client.app.include_router(router)
    return client, factory


def test_five_sections_and_waf_search_before_pagination(access):
    client, factory = access
    run = seed(factory)
    response = client.get("/api-access")
    assert response.status_code == 200 and f"snapshot={run}" in str(response.url)
    assert "49 results" in response.text and "5 of 5 API sections" in response.text
    assert (
        "request or timeout counts" in response.text
        and "IP geolocation" in response.text
    )
    assert "Latest imported snapshot" in response.text
    assert "192.0.2.10" in response.text and "0000" in response.text
    assert "Authentication API" in response.text
    matched = client.get(
        "/api-access", params={"snapshot": run, "agent": AGENT, "ip": "192.0.2.10"}
    )
    assert "25 results" in matched.text and "Other/1.0" not in matched.text
    assert (
        "49 results"
        in client.get("/api-access", params={"q": "API", "snapshot": run}).text
    )
    assert (
        "0 results"
        in client.get("/api-access", params={"q": "%", "snapshot": run}).text
    )
    assert (
        "1 results"
        in client.get(
            "/api-access",
            params={"snapshot": run, "service": "Authentication API Versions"},
        ).text
    )
    assert client.get("/api-access?snapshot=&from_date=&to_date=").status_code == 200
    assert (
        "0 results"
        in client.get(
            "/api-access", params={"snapshot": run, "from_date": "2026-11-25"}
        ).text
    )
    assert client.get("/api-access?from_date=2026-99-99").status_code == 422
    assert (
        client.get("/api-access?from_date=2026-11-25&to_date=2026-11-24").status_code
        == 422
    )
    assert client.get("/api-access?service=arbitrary").status_code == 422
    assert client.get("/api-access?snapshot=9999").status_code == 404
    with factory() as session:
        row = session.scalar(
            select(StagingRow)
            .join(StagingDataset)
            .where(StagingDataset.source_dataset_name == "Authentication API Versions")
        )
        evidence = client.get(f"/api-access/{row.id}/source")
        assert AGENT in evidence.text and "Last API Request" in evidence.text
        assert row.raw_row_json["Client Id"] == "00000"
    assert client.get("/api-access/99999/source").status_code == 404


def test_snapshot_scope_failed_delivery_missing_sections_and_originals(access):
    client, factory = access
    old = seed(factory, day=date(2026, 11, 23), count=2)
    new = seed(factory, count=4, omit={"Authentication API Versions"})
    seed(factory, day=date(2026, 11, 26), status="failed")
    page = client.get("/api-access")
    assert f"snapshot={new}" in str(page.url) and "4 results" in page.text
    assert "Not supplied in this delivery: Authentication API" in page.text
    assert "3 results" in client.get(f"/api-access?snapshot={old}").text
    with factory() as session:
        nonapi = session.scalar(
            select(StagingRow)
            .join(StagingDataset)
            .where(StagingDataset.source_dataset_name == "Organisations")
        )
        assert client.get(f"/api-access/{nonapi.id}/source").status_code == 404


def test_saved_conditions_sorting_all_pages_and_snapshot_qualified_links(access):
    client, factory = access
    run = seed(factory)
    with factory.begin() as session:
        session.add(ImportMutex(import_key=MUTEX))
    publish_participants(factory, run, "synthetic")
    page = client.get(f"/api-access?snapshot={run}")
    assert 'href="/organisations/1"' in page.text and 'href="/locations/1"' in page.text
    schema = [
        {"key": f"c{i}", "label": label}
        for i, label in enumerate(
            [
                *HEADERS,
                "API service",
                "API version",
                "Requested API version",
                "Last request date",
                "Evidence",
            ]
        )
    ]
    created = save(
        client,
        key="api-access",
        schema=schema,
        command="create",
        name="Java clients",
        config={
            "conditions": [{"field": "c5", "operator": "contains", "value": AGENT}],
            "sort": "c4",
            "direction": "desc",
        },
    )
    assert created.status_code == 200
    vid = created.json()["view"]["id"]
    page = client.get(
        "/api-access", params={"snapshot": run, "tv_api-access_view": vid}
    )
    assert (
        page.status_code == 200
        and "25 results" in page.text
        and "Other/1.0" not in page.text
    )
    assert page.text.index("00046") < page.text.index("0000")
    other = seed(factory, day=date(2026, 11, 26), count=2)
    historical = client.get(f"/api-access?snapshot={other}")
    assert 'href="/organisations/1"' not in historical.text
    api = client.get("/table-views/api-access", params={"schema": json.dumps(schema)})
    assert (
        api.json()["server_filtered"] is True
        and api.json()["fields"][11]["type"] == "date"
    )


def test_empty_state_is_not_a_fake_access_log(access):
    client, _ = access
    page = client.get("/api-access")
    assert page.status_code == 200 and "No successfully imported snapshot" in page.text
    assert "0 results" in page.text


def test_staff_boundary_does_not_expose_access_or_originals(access, monkeypatch):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.db.session import get_session
    from app.portal import auth_access

    _, factory = access
    app = FastAPI()
    auth_access.install_portal_access(
        app,
        SimpleNamespace(
            portal_auth_enabled=True,
            portal_auth_origin="https://testserver",
            environment="production",
        ),
    )
    app.include_router(router)

    def dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = dependency
    monkeypatch.setattr(auth_access, "principal", lambda _: None)
    with TestClient(app, base_url="https://testserver", follow_redirects=False) as client:
        for url in ["/api-access", "/api-access/1/source"]:
            assert client.get(url).status_code == 303
        monkeypatch.setattr(
            auth_access,
            "principal",
            lambda _: SimpleNamespace(is_admin=True, is_nmvo=False),
        )
        assert client.get("/api-access").status_code == 403
        assert client.get("/api-access/1/source").status_code == 403
        monkeypatch.setattr(
            auth_access,
            "principal",
            lambda _: SimpleNamespace(is_admin=False, is_nmvo=True),
        )
        assert client.get("/api-access/99999/source").status_code == 404


def test_latest_missing_sections_never_reuses_stale_data_and_dates_exclude_missing(
    access,
):
    client, factory = access
    old = seed(factory, count=1)
    with factory.begin() as session:
        row = session.scalar(
            select(StagingRow)
            .join(StagingDataset)
            .where(StagingDataset.source_dataset_name == "Authentication API Versions")
        )
        row.raw_row_json = dict(
            row.raw_row_json,
            **{"Last API Request": "", "User-Agent": "<script>unsafe()</script>"},
        )
    assert (
        "1 results" in client.get(f"/api-access?snapshot={old}&to_date=2026-11-25").text
    )
    assert (
        "&lt;script&gt;unsafe()&lt;/script&gt;"
        in client.get(f"/api-access?snapshot={old}").text
    )
    new = seed(factory, day=date(2026, 11, 26), omit=set(SERVICES))
    page = client.get("/api-access")
    assert f"snapshot={new}" in str(page.url) and "0 results" in page.text
    assert "0 of 5 API sections" in page.text
