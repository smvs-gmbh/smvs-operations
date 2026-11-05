import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.db.models import Base, ImportMutex
from app.core.db.session import GuardedSession, get_session
from app.domain.mapping import MUTEX, publish
from app.portal.routes import router
from tests.domain.test_mapping import datasets, seed


@pytest.fixture
def portal(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "portal.db"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.create_function("DATABASE", 0, lambda: "smvs_operations")

    Base.metadata.create_all(engine)
    factory = sessionmaker(
        engine,
        class_=GuardedSession,
        configured_database="smvs_operations",
        expire_on_commit=False,
    )
    with factory() as s:
        s.add(ImportMutex(import_key=MUTEX))
        s.commit()
    app = FastAPI()
    app.include_router(router)
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/portal-static",
        StaticFiles(
            directory=str(Path(__file__).resolve().parents[2] / "app/portal/static")
        ),
        name="portal_static",
    )

    def dependency():
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = dependency
    with TestClient(app) as client:
        yield client, factory
    engine.dispose()


def test_portal_empty_state_and_root_redirect(portal):
    client, _ = portal
    assert client.get("/").status_code == 200
    assert "No product/batch dataset" in client.get("/products").text


def test_swiss_only_names_search_filter_and_detail(portal):
    client, factory = portal
    publish(factory, *seed(factory), "synthetic-nmvs")
    page = client.get("/products")
    assert page.status_code == 200
    assert "Schweizer Präparat" in page.text and "Schweizer Inhaberin" in page.text
    assert "WRONG NMVS NAME" not in page.text and "WRONG NMVS MAH" not in page.text
    assert "No matching products" in client.get("/products?q=WRONG").text
    assert "No matching products" in client.get("/products?status=no_sai_match").text
    assert "Schweizer Präparat" in client.get("/products?q=Schweizer").text
    detail = client.get("/products/1")
    assert detail.status_code == 200 and "Lot-001" in detail.text
    assert "Referenced by batches only" in detail.text
    assert "270000" in detail.text
    assert "Emballage suisse" in detail.text
    assert client.get("/products/99999").status_code == 404


def test_batches_are_searchable_and_unknown_versions_visible(portal):
    client, factory = portal
    publish(factory, *seed(factory, datasets(batch_version="-2")), "synthetic-nmvs")
    page = client.get("/batches?q=Lot-001")
    assert page.status_code == 200 and "Lot-001" in page.text
    assert "Unresolved" in page.text and "-2" in page.text
    assert "Schweizer Präparat" in page.text and "WRONG NMVS" not in page.text
    assert "No matching batches" in client.get("/batches?q=does-not-exist").text


def test_xss_and_sql_wildcards_are_not_executed_or_expanded(portal):
    client, factory = portal
    data = datasets()
    data["SAI_PRAEPARATE"][0]["PRAEPARATENAME"] = '<script>alert("x")</script>'
    publish(factory, *seed(factory, data), "synthetic-nmvs")
    html = client.get("/products").text
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "No matching products" in client.get("/products", params={"q": "%"}).text
    assert (
        "No matching products"
        in client.get("/products", params={"q": "' OR 1=1 --"}).text
    )


def test_pagination_and_parameter_validation(portal):
    client, factory = portal
    data = datasets()
    for i in range(44):
        prefix = f"7610000{i:05d}"
        check = (
            -sum(int(c) * (3 if j % 2 == 0 else 1) for j, c in enumerate(prefix[::-1]))
        ) % 10
        data["Products"].append(
            {**data["Products"][0], "Product Code": prefix + str(check)}
        )
    publish(factory, *seed(factory, data), "synthetic-nmvs")
    assert "Page 1 / 2" in client.get("/products").text
    assert "Page 2 / 2" in client.get("/products?page=2").text
    assert client.get("/products?page=0").status_code == 422
    assert client.get("/products?status=foreign").status_code == 422


def test_original_product_source_is_separate_and_complete(portal):
    client, factory = portal
    data = datasets(version="-1", batch_version="-2")
    data["Products"][0]["Creation Date"] = "2001-01-02T03:04:05"
    data["Products"][0]["Strength"] = "Source strength exactly"
    publish(factory, *seed(factory, data), "synthetic-nmvs")
    swiss = client.get("/products/1")
    original = client.get("/products/1/source")
    assert swiss.status_code == original.status_code == 200
    assert "WRONG NMVS NAME" not in swiss.text
    assert "WRONG NMVS NAME" in original.text and "WRONG NMVS MAH" in original.text
    assert (
        "2001-01-02T03:04:05" in original.text
        and "Source strength exactly" in original.text
    )
    assert "Creation Date" in original.text and "Source value retained" in original.text
    assert "Schweizer Präparat" in client.get("/products?version=-1").text
    assert "No matching products" in client.get("/products?version=-2").text
    batches = client.get("/batches?version=-2")
    assert "Lot-001" in batches.text
    raw_batch = client.get("/batches/1/source")
    assert (
        raw_batch.status_code == 200
        and "-2" in raw_batch.text
        and "270000" in raw_batch.text
    )


def test_retained_full_original_product_survives_staging_expiry(portal):
    from sqlalchemy import select

    from app.core.db.models import StagingRow
    from app.domain.models import ProductSourceRecord

    client, factory = portal
    publish(factory, *seed(factory), "synthetic-nmvs")
    with factory() as s:
        source = s.scalar(select(ProductSourceRecord))
        staging_id = source.source_row_id
        source.source_row_id = None
        s.flush()
        s.delete(s.get(StagingRow, staging_id))
        s.commit()
    response = client.get("/products/1/source")
    assert response.status_code == 200 and "WRONG NMVS NAME" in response.text
    assert "Retained source values" in response.text
    assert "nur ein Auszug" not in response.text
