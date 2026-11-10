import json
from types import SimpleNamespace

import pytest
from fastapi import Request
from sqlalchemy import select

from app.core.db.session import get_session
from app.domain.mapping import publish
from app.domain.models import PortalUser, ProductSourceRecord
from app.portal.table_views import router
from tests.domain.test_mapping import datasets, seed

SCHEMA = [
    {"key": f"c{i}", "label": label}
    for i, label in enumerate(["Product", "GTIN", "MAH", "Version", "Match", "Links"])
]


@pytest.fixture
def tables(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory.begin() as session:
        session.add_all(
            [
                PortalUser(
                    id=i,
                    email=f"{i}@example.test",
                    handle=str(i),
                    is_admin=0,
                    is_nmvo=1,
                )
                for i in (1, 2)
            ]
        )

    def identity(request: Request):
        with factory() as session:
            request.state.portal_user = SimpleNamespace(
                id=int(request.headers.get("x-user", "1"))
            )
            yield session

    client.app.dependency_overrides[get_session] = identity
    return client, factory


def save(client, key="products", schema=SCHEMA, **values):
    return client.post(
        "/table-views/" + key,
        params={"schema": json.dumps(schema)},
        headers={"origin": "http://testserver"},
        data={k: json.dumps(v) if k == "config" else v for k, v in values.items()},
    )


def test_private_views_and_validation(tables):
    client, _ = tables
    result = save(
        client,
        command="create",
        name="Versions",
        config={
            "conditions": [{"field": "c3", "operator": "greater_than", "value": "2"}]
        },
    )
    assert result.status_code == 200
    view = result.json()["view"]
    own = client.get(
        "/table-views/products",
        params={"schema": json.dumps(SCHEMA), "tv_products_view": view["id"]},
    )
    assert own.status_code == 200 and own.json()["selected"]["id"] == view["id"]
    assert (
        client.get(
            "/table-views/products",
            params={"schema": json.dumps(SCHEMA), "tv_products_view": view["id"]},
            headers={"x-user": "2"},
        ).status_code
        == 404
    )
    assert (
        save(
            client, command="save", id=view["id"], version=0, name="stale", config={}
        ).status_code
        == 409
    )
    assert (
        save(
            client,
            command="preview",
            config={
                "conditions": [
                    {"field": "DROP TABLE", "operator": "equals", "value": "x"}
                ]
            },
        ).status_code
        == 422
    )
    assert (
        save(
            client,
            command="preview",
            config={
                "conditions": [
                    {"field": "c3", "operator": "greater_than", "value": "NaN"}
                ]
            },
        ).status_code
        == 422
    )
    assert (
        save(client, command="preview", config={"columns": ["c1"]}).status_code == 422
    )


def test_conditions_count_before_pagination_and_keep_detail_navigation(tables):
    client, factory = tables
    data = datasets()
    for i in range(55):
        data["Products"].append(
            {
                **data["Products"][0],
                "Product Code": f"unknown-{i:03}",
                "Product Version": str(i),
            }
        )
    publish(factory, *seed(factory, data), "synthetic-nmvs")
    # Use retained numeric versions for records whose names cannot be SAI-matched.
    with factory.begin() as session:
        records = list(
            session.scalars(
                select(ProductSourceRecord).order_by(ProductSourceRecord.id)
            )
        )
        for i, record in enumerate(records):
            record.reported_version = i
    view = save(
        client,
        command="create",
        name="Last versions",
        config={
            "conditions": [{"field": "c3", "operator": "greater_than", "value": "50"}],
            "sort": "c3",
            "direction": "desc",
        },
    ).json()["view"]
    page = client.get("/products", params={"tv_products_view": view["id"]})
    assert page.status_code == 200
    assert "5 results" in page.text
    with factory() as session:
        ordered = list(
            session.scalars(
                select(ProductSourceRecord.id)
                .where(ProductSourceRecord.reported_version > 50)
                .order_by(ProductSourceRecord.reported_version.desc())
            )
        )
    detail = client.get(
        f"/products/{ordered[0]}", params={"tv_products_view": view["id"]}
    )
    assert detail.status_code == 200
    assert f'rel="next" href="/products/{ordered[1]}' in detail.text
    assert "tv_products_view=" in detail.text


def test_default_view_restores_scope_and_other_tables_are_independent(tables):
    client, _ = tables
    result = save(
        client,
        command="create",
        name="Default",
        is_default="true",
        config={"quick_filters": {"status": "matched_sai", "q": ""}},
    )
    assert result.status_code == 200
    response = client.get("/products", follow_redirects=False)
    assert (
        response.status_code == 303
        and "status=matched_sai" in response.headers["location"]
    )
    assert (
        client.get("/products?tv_products_view=all", follow_redirects=False).status_code
        == 200
    )
    report_schema = [{"key": "c0", "label": "Source"}, {"key": "c1", "label": "Status"}]
    report = save(
        client,
        key="t-report",
        schema=report_schema,
        command="create",
        name="My report",
        config={},
    )
    assert report.status_code == 200
    assert (
        client.get(
            "/table-views/t-other",
            params={
                "schema": json.dumps(report_schema),
                "tv_t-other_view": report.json()["view"]["id"],
            },
        ).status_code
        == 404
    )


def test_related_tables_filter_the_complete_scope(tables):
    from app.core.db.models import ImportMutex
    from app.domain.participants.mapping import MUTEX, publish_participants
    from app.portal.participant_routes import router as participants
    from tests.domain.test_participants import source

    client, factory = tables
    client.app.include_router(participants)
    with factory.begin() as session:
        session.add(ImportMutex(import_key=MUTEX))
    publish(factory, *seed(factory), "synthetic-nmvs")
    publish_participants(factory, source(factory), "synthetic-nmvs")
    for path, key, column in [
        ("/products/1", "product-batches", "c3"),
        ("/organisations/1", "organisation-locations", "c2"),
    ]:
        response = client.get(
            path,
            params={
                f"tv_{key}_rules": json.dumps(
                    [{"field": column, "operator": "equals", "value": "does not exist"}]
                ),
            },
        )
        assert response.status_code == 200
        assert (
            "No matching batches found."
            if key == "product-batches"
            else "No Locations found"
        ) in response.text
    assert "Synthetic location" in client.get("/organisations/1").text


def test_exception_schema_survives_empty_selection_and_sai_lookup(tables):
    from app.core.db.models import ImportMutex
    from app.domain.exceptions.mapping import MUTEX, publish_exceptions
    from app.portal.exception_routes import router as exceptions
    from tests.integration.exceptions.test_exceptions import NS, acquire, alert, page

    client, factory = tables
    client.app.include_router(exceptions)
    with factory.begin() as session:
        session.add(ImportMutex(import_key=MUTEX))
    publish(factory, *seed(factory), NS)
    publish_exceptions(factory, acquire(factory, [page([alert()])]), NS)
    schema = [{"key": f"c{i}", "label": str(i)} for i in range(6)]
    saved = save(
        client,
        key="exceptions",
        schema=[{"key": "selection", "label": "Select"}, *schema],
        command="create",
        name="Swiss names",
        config={
            "conditions": [
                {"field": "c3", "operator": "contains", "value": "Schweizer"}
            ],
        },
    ).json()["view"]
    settings = client.get(
        "/table-views/exceptions",
        params={"schema": json.dumps(schema), "tv_exceptions_view": saved["id"]},
    )
    assert settings.status_code == 200
    assert "selection" in settings.json()["config"]["columns"]
    response = client.get(
        "/exceptions",
        params={
            "tv_exceptions_view": saved["id"],
            "start": "2026-10-01",
            "end": "2026-10-31",
        },
    )
    assert response.status_code == 200 and "CH-test-001" in response.text
