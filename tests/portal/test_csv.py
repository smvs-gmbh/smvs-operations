import csv
import hashlib
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import Request
from sqlalchemy import select

from app.core.db.session import get_session
from app.domain.models import PortalCsvExport, PortalUser
from app.portal.csv_routes import router


@pytest.fixture
def csv_portal(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory.begin() as session:
        session.add(PortalUser(id=1, email="export@example.test", handle="export", is_nmvo=1, is_admin=0))
    actor = SimpleNamespace(id=1, is_nmvo=True, is_admin=False)

    def dependency(request: Request):
        request.state.portal_user = actor
        with factory() as session:
            yield session

    client.app.dependency_overrides[get_session] = dependency
    return client, factory, actor


def payload(**extra):
    return {
        "source_path": "/products", "table_key": "products", "view_hash": "a" * 64,
        "columns": [{"key": "c1", "label": "GTIN14"}, {"key": "c0", "label": "Product"}],
        "rows": [["07680548790019", 'Schweizer Produkt, "CH"\nZweite Zeile'], ["00042", "Crème brûlée"]],
        **extra,
    }


def post(client, data, origin="http://testserver"):
    return client.post("/table-exports/csv", json=data, headers={"origin": origin})


def test_csv_preserves_displayed_columns_order_text_and_has_audit_receipt(csv_portal):
    client, factory, _ = csv_portal
    data = payload()
    response = post(client, data)
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")))) == [
        ["GTIN14", "Product"], *data["rows"],
    ]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="products-' in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('UTC.csv"')
    with factory() as session:
        receipt = session.scalar(select(PortalCsvExport))
        assert receipt.actor_id == 1 and receipt.source_path == "/products"
        assert receipt.columns == data["columns"] and receipt.row_count == 2
        assert receipt.file_sha256 == hashlib.sha256(response.content).hexdigest()
        assert receipt.byte_count == len(response.content)
        assert response.headers["x-export-receipt"] == str(receipt.id)
        assert "Schweizer Produkt" not in json.dumps(receipt.columns)


def test_csv_empty_view_formula_text_and_invalid_requests(csv_portal, monkeypatch):
    from app.portal import csv_routes

    client, factory, _ = csv_portal
    empty = post(client, payload(rows=[]))
    assert empty.status_code == 200
    assert list(csv.reader(io.StringIO(empty.content.decode("utf-8-sig")))) == [["GTIN14", "Product"]]
    text = post(client, payload(rows=[["00042", '=HYPERLINK("https://example.test")'], ["00043", "  +CMD"]]))
    assert text.status_code == 200
    rows = list(csv.reader(io.StringIO(text.content.decode("utf-8-sig"))))
    assert rows[1][0] == "00042" and rows[1][1].startswith("'=") and rows[2][1].startswith("'  +")
    for invalid in (payload(rows=[["too few"]]), payload(rows=[[1, "not string"]]), payload(source_path="https://other.test"), payload(source_path="//other.test"), payload(table_key="bad\r\nname"), payload(columns=[]), payload(view_hash="wrong")):
        assert post(client, invalid).status_code == 422
    with factory() as session:
        assert len(session.scalars(select(PortalCsvExport)).all()) == 2
    monkeypatch.setattr(csv_routes, "MAX_REQUEST_BYTES", 20)
    assert post(client, payload()).status_code == 413


def test_csv_requires_staff_origin_and_retained_receipt(csv_portal, monkeypatch):
    from app.core.db.session import GuardedSession

    client, factory, actor = csv_portal
    assert post(client, payload(), origin="https://other.test").status_code == 403
    actor.is_nmvo = False
    assert post(client, payload()).status_code == 403
    actor.is_admin = True
    assert post(client, payload()).status_code == 403
    assert post(client, payload(source_path="/admin/users")).status_code == 200
    actor.is_nmvo = True

    def broken_commit(session):
        raise RuntimeError("Audit store unavailable")

    monkeypatch.setattr(GuardedSession, "commit", broken_commit)
    with pytest.raises(RuntimeError, match="Audit store unavailable"):
        post(client, payload())
    with factory() as session:
        assert len(session.scalars(select(PortalCsvExport)).all()) == 1


def test_csv_receipt_migration_refuses_to_discard_retained_export_history(csv_portal):
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    from tests.core.test_artifact_content_migration import load_migration

    client, factory, _ = csv_portal
    assert post(client, payload()).status_code == 200
    migration = load_migration("0052_portal_csv_exports")
    with factory() as session:
        migration.op = Operations(MigrationContext.configure(session.connection()))
        with pytest.raises(RuntimeError, match="Retain CSV export audit receipts"):
            migration.downgrade()
        assert session.scalar(select(PortalCsvExport)) is not None


def test_excel_keeps_identifiers_as_text_and_pack_counts_as_numbers(csv_portal):
    from openpyxl import load_workbook

    client, factory, _ = csv_portal
    data = payload(columns=[
        {"key": "c1", "label": "GTIN14", "type": "text"},
        {"key": "c2", "label": "Serial number", "type": "text"},
        {"key": "c3", "label": "Packs", "type": "number"},
        {"key": "c4", "label": "Source message", "type": "text"},
    ], rows=[
        ["07680548790019", "00099169496176896506", "1’234", '=HYPERLINK("https://example.test")'],
        ["07680548790415", "01-02", "0", "Crème, CH"],
    ])
    response = client.post("/table-exports/xlsx", json=data, headers={"origin": "http://testserver"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.headers["content-disposition"].endswith('UTC.xlsx"')
    book = load_workbook(io.BytesIO(response.content), data_only=False)
    sheet = book.active
    assert sheet["A2"].value == "07680548790019" and sheet["A2"].data_type == "s"
    assert sheet["A2"].number_format == "@"
    assert sheet["B2"].value == "00099169496176896506" and sheet["B2"].data_type == "s"
    assert sheet["B3"].value == "01-02" and sheet["B3"].data_type == "s"
    assert sheet["C2"].value == 1234 and sheet["C2"].data_type == "n"
    assert sheet["C3"].value == 0
    assert sheet["D2"].value == data["rows"][0][3] and sheet["D2"].data_type == "s"
    assert not any(cell.data_type == "f" for row in sheet for cell in row)
    assert sheet.freeze_panes == "A2" and sheet.auto_filter.ref == "A1:D3"
    assert sheet.column_dimensions["A"].width >= 16
    book.close()
    with factory() as session:
        receipt = session.scalar(select(PortalCsvExport))
        assert receipt.file_format == "xlsx" and receipt.row_count == 2
        assert receipt.file_sha256 == hashlib.sha256(response.content).hexdigest()


def test_excel_does_not_round_or_silently_truncate_source_values(csv_portal):
    from openpyxl import load_workbook

    client, factory, _ = csv_portal
    data = payload(columns=[
        {"key": "id", "label": "GTIN14", "type": "number"},
        {"key": "amount", "label": "Amount", "type": "number"},
    ], rows=[["7680548790019", "12345678901234567"], ["00042", "12.5"]])
    response = client.post("/table-exports/xlsx", json=data, headers={"origin": "http://testserver"})
    assert response.status_code == 200
    book = load_workbook(io.BytesIO(response.content))
    assert book.active["A2"].value == "7680548790019" and book.active["A2"].data_type == "s"
    assert book.active["A3"].value == "00042"
    assert book.active["B2"].value == "12345678901234567" and book.active["B2"].data_type == "s"
    assert book.active["B3"].value == 12.5
    book.close()
    for value in ("x" * 32768, "bad\x01value"):
        result = client.post("/table-exports/xlsx", json=payload(rows=[["00042", value]]), headers={"origin": "http://testserver"})
        assert result.status_code == 422 and "Download CSV" in result.json()["detail"]
    with factory() as session:
        assert len(session.scalars(select(PortalCsvExport)).all()) == 1


def test_export_format_migration_preserves_old_csv_receipts_and_guards_excel_provenance():
    import sqlalchemy as sa
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    from tests.core.test_artifact_content_migration import load_migration

    engine = sa.create_engine("sqlite://")
    migration = load_migration("0053_table_export_format")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE portal_csv_exports (id INTEGER PRIMARY KEY, file_sha256 VARCHAR(64))")
        connection.exec_driver_sql("INSERT INTO portal_csv_exports VALUES (1, 'retained-checksum')")
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert connection.exec_driver_sql("SELECT id,file_sha256,file_format FROM portal_csv_exports").one() == (1, "retained-checksum", "csv")
        connection.exec_driver_sql("INSERT INTO portal_csv_exports VALUES (2, 'excel-checksum', 'xlsx')")
        with pytest.raises(RuntimeError, match="Retain Excel export format provenance"):
            migration.downgrade()
        assert connection.exec_driver_sql("SELECT count(*) FROM portal_csv_exports").scalar() == 2
    engine.dispose()
