# ruff: noqa: F811 -- imported pytest fixture
import json

import pytest
from sqlalchemy import func, select

from app.core.db.models import StagingRow
from app.domain.crm.declaration_lookup import declaration_values
from app.domain.crm.imports import parse_export, stage_export
from app.domain.crm.integrity import check_integrity
from app.domain.crm.self_declarations import seed_self_declarations
from app.domain.models import (
    CRMAgreement,
    CRMContact,
    CRMEndUser,
    CRMListView,
    CRMMah,
    CRMSelfDeclaration,
)
from app.integration.artifacts.storage import utcnow
from app.portal.crm_field_catalogue import catalogue_context
from tests.portal.test_crm_views import post_view, views_portal  # noqa: F401


def seed(factory):
    data = b"Record Id,MAH Name,Declaration year,RX packs sold,RX sales group\nA-old,Alpha,2024,120000,JG-3\nA-new,Alpha,2025,0,JG-0\nB-one,Beta,2025,55,JG-3\nB-two,Beta,2025,66,JG-10\nC-old,Gamma,2024,,JG-1\nUnassigned,Nobody,2025,7,JG-0\n"
    with factory() as s:
        mahs = [
            CRMMah(
                name=n,
                contract_status="unknown",
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            for n in ("Alpha", "Beta", "Gamma")
        ]
        s.add_all(mahs)
        s.flush()
        dataset, _ = stage_export(
            s,
            parse_export("Self-declarations", data),
            data,
            "synthetic-declarations.csv",
        )
        rows = list(
            s.scalars(
                select(StagingRow)
                .where(StagingRow.staging_dataset_id == dataset.id)
                .order_by(StagingRow.source_row_number)
            )
        )
        for i, (source, mah) in enumerate(
            zip(rows, (mahs[0], mahs[0], mahs[1], mahs[1], mahs[2], None), strict=True)
        ):
            raw = source.raw_row_json
            s.add(
                CRMSelfDeclaration(
                    source_key=f"synthetic-{i}",
                    source_row_id=source.id,
                    mah_id=mah.id if mah else None,
                    record_label=raw["Record Id"],
                    source_mah_name=raw["MAH Name"],
                    declaration_year=int(raw["Declaration year"]),
                    packs_sold=int(raw["RX packs sold"])
                    if raw["RX packs sold"]
                    else None,
                )
            )
        s.commit()
        return [m.id for m in mahs]


def test_lookup_discriminator_keeps_one_source_and_distinguishes_zero_missing_conflict(
    views_portal,
):
    client, factory = views_portal
    ids = seed(factory)
    with factory() as s:
        values = declaration_values(s, ids)
        assert (
            values[ids[0]]["sd_packs"] == 0
            and values[ids[0]]["sd_sales_group"] == "JG-0"
        )
        assert values[ids[0]]["sd_year"] == 2025
        assert values[ids[1]]["sd_selection"].startswith("Data error")
        assert (
            values[ids[1]]["sd_packs"] is None
            and values[ids[1]]["sd_sales_group"] is None
        )
        exact = declaration_values(s, ids, {"rule": "year", "year": 2024})
        assert (
            exact[ids[0]]["sd_packs"] == 120000
            and exact[ids[0]]["sd_sales_group"] == "JG-3"
        )
        assert exact[ids[1]]["sd_selection"] == "No declaration"
        assert exact[ids[2]]["sd_packs"] is None
        context = catalogue_context(
            s,
            "mahs",
            [s.get(CRMMah, ids[0])],
            declaration_lookup={"rule": "year", "year": 2024},
        )
        assert context["crm_field_cells"][ids[0]]["sd_packs"] == "120’000"
    page = client.get(
        "/crm/mahs",
        params={"declaration_lookup": json.dumps({"rule": "year", "year": 2024})},
    )
    assert (
        page.status_code == 200
        and "120’000" in page.text
        and "Data year 2024" in page.text
    )
    assert "declaration_lookup=" in page.text
    assert "Self-declaration lookup" in client.get(f"/crm/mahs/{ids[0]}").text


def test_lookup_views_filter_sort_before_pagination_and_preserve_selection(
    views_portal,
):
    client, factory = views_portal
    ids = seed(factory)
    config = {
        "declaration_lookup": {"rule": "year", "year": 2024},
        "columns": ["name", "sd_year", "sd_packs"],
        "conditions": [
            {"field": "sd_packs", "operator": "greater_than", "value": "10"}
        ],
        "sort": "sd_packs",
        "direction": "desc",
    }
    response = post_view(client, command="create", name="Lookup trial", config=config)
    assert response.status_code == 200
    view = response.json()["view"]
    assert view["config"]["declaration_lookup"] == config["declaration_lookup"]
    assert "sd_selection" in view["config"]["columns"]
    page = client.get(
        "/crm/mahs", params={"view": view["id"]}, headers={"x-test-user": "1"}
    )
    assert (
        page.status_code == 200 and "1 results" in page.text and "120’000" in page.text
    )
    assert f"/crm/mahs/{ids[1]}?" not in page.text
    assert (
        client.get(
            "/crm/views/mahs", params={"view": view["id"]}, headers={"x-test-user": "2"}
        ).status_code
        == 404
    )
    for invalid in (
        {"rule": "year", "year": True},
        {"rule": "year", "year": "2025"},
        {"rule": "sum"},
        {"rule": "latest", "year": 2025},
        {"rule": "year", "year": 2025, "sql": "SELECT 1"},
    ):
        assert (
            post_view(
                client, command="preview", config={"declaration_lookup": invalid}
            ).status_code
            == 422
        )
    assert (
        post_view(
            client,
            directory="contacts",
            command="preview",
            config={"declaration_lookup": {"rule": "latest"}},
        ).status_code
        == 422
    )
    assert client.get("/crm/mahs?declaration_lookup=oops").status_code == 422


def test_integrity_is_read_only_and_contact_roles_are_independent(views_portal):
    client, factory = views_portal
    ids = seed(factory)
    with factory() as s:
        good = CRMContact(airtable_id="good", label="good@example.test")
        archived = CRMContact(
            airtable_id="archived", label="old@example.test", archived_at=utcnow()
        )
        orphan = CRMContact(airtable_id="orphan", label="Orphan contact")
        pending = CRMContact(
            airtable_id="pending",
            label="Pending",
            profile={"registration_pending": True},
        )
        s.add_all([good, archived, orphan, pending])
        s.flush()
        a, b, c = [s.get(CRMMah, i) for i in ids]
        a.profile = {"spoc_ids": [good.id], "alert_contact_ids": [good.id]}
        b.profile = {
            "spoc_id": archived.id,
            "alert_contact_ids": [999999, {"invalid": "reference"}],
        }
        c.profile = {"eligible_for_invoicing": True}
        agreement = CRMAgreement(
            contract_id="Signed-test", contractor="Gamma", status="Signed", mahs=[c]
        )
        s.add(agreement)
        # A contact assigned to an End User must not be reported as orphaned.
        end_contact = CRMContact(airtable_id="end-contact", label="eu@example.test")
        s.add(end_contact)
        s.flush()
        s.add(CRMEndUser(name="End User", profile={"spoc_ids": [end_contact.id]}))
        s.commit()
        result = check_integrity(s, 2025)
        findings = result["findings"]
        assert any(f["rule"] == "sd_duplicate" and f["id"] == ids[1] for f in findings)
        assert any(f["rule"] == "sd_missing" and f["id"] == ids[2] for f in findings)
        assert not any(
            f["id"] == ids[0] and f["rule"] in ("mah_spoc", "mah_alert_manager")
            for f in findings
        )
        assert any(
            f["id"] == ids[1] and f["rule"] == "contact_reference" for f in findings
        )
        orphans = [f["id"] for f in findings if f["rule"] == "contact_orphan"]
        assert (
            orphan.id in orphans
            and end_contact.id not in orphans
            and pending.id not in orphans
        )
        counts = {
            model.__tablename__: s.scalar(select(func.count()).select_from(model))
            for model in (CRMMah, CRMContact, CRMSelfDeclaration, CRMListView)
        }
    page = client.get("/crm/integrity?rule=sd_duplicate&year=2025")
    assert page.status_code == 200 and "2 declarations for data year 2025" in page.text
    assert (
        "Data integrity" in page.text
        and "No maintained assignment or imported relation reference was found."
        not in page.text
    )
    assert client.get("/crm/integrity?rule=unknown").status_code == 422
    assert client.post("/crm/integrity").status_code == 405
    with factory() as s:
        assert counts == {
            model.__tablename__: s.scalar(select(func.count()).select_from(model))
            for model in (CRMMah, CRMContact, CRMSelfDeclaration, CRMListView)
        }


def test_import_rejects_duplicate_pairs_atomically_but_keeps_staged_evidence(
    views_portal,
):
    _, factory = views_portal
    data = b"Record Id,MAH Name,Declaration year,RX packs sold\nOne,Unique,2025,1\nTwo,Unique,2025,2\n"
    with factory() as s:
        s.add(
            CRMMah(
                name="Unique",
                contract_status="unknown",
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        s.commit()
        dataset, _ = stage_export(
            s, parse_export("Self-declarations", data), data, "duplicate-source.csv"
        )
        s.commit()
        with pytest.raises(ValueError, match="Duplicate self-declaration"):
            seed_self_declarations(s, dataset.id)
        assert not s.new
        assert s.scalar(select(func.count()).select_from(CRMSelfDeclaration)) == 0
        assert (
            s.scalar(
                select(func.count())
                .select_from(StagingRow)
                .where(StagingRow.staging_dataset_id == dataset.id)
            )
            == 2
        )


def test_lookup_ordering_spans_pages_and_export_page_requests(views_portal):
    client, factory = views_portal
    with factory() as s:
        for i in range(45):
            mah = CRMMah(
                name=f"Paging {i:02}",
                contract_status="unknown",
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            s.add(mah)
            s.flush()
            s.add(
                CRMSelfDeclaration(
                    source_key=f"page-{i}",
                    mah_id=mah.id,
                    record_label=f"SD-{i}",
                    source_mah_name=mah.name,
                    declaration_year=2024,
                    packs_sold=i,
                )
            )
        s.commit()
    params = {
        "declaration_lookup": json.dumps({"rule": "year", "year": 2024}),
        "sort": "sd_packs",
        "direction": "desc",
        "rules": json.dumps(
            [{"field": "sd_packs", "operator": "greater_than", "value": "0"}]
        ),
    }
    page = client.get("/crm/mahs", params=params)
    assert page.status_code == 200 and "44 results" in page.text
    assert "Paging 44" in page.text and "Paging 01" not in page.text
    tail = client.get("/crm/mahs", params=params | {"page": 2})
    assert (
        "Paging 01" in tail.text
        and "Paging 44" not in tail.text
        and "Paging 00" not in tail.text
    )
    export = client.get("/crm/mahs", params=params, headers={"X-Portal-CSV": "1"})
    assert (
        export.status_code == 200
        and "Paging 44" in export.text
        and "Paging 01" in export.text
    )
    missing = client.get(
        "/crm/mahs",
        params=params
        | {"declaration_lookup": json.dumps({"rule": "year", "year": 2023})},
    )
    assert missing.status_code == 200 and "0 results" in missing.text


def test_imported_contact_relations_and_invalid_role_emails_are_review_items(
    views_portal,
):
    _, factory = views_portal
    data = b"RECORD_ID2,Record Id,Email,Link IT Supplier\nsource-contact,Supplier contact,supplier@example.test,Supplier\n"
    with factory() as s:
        dataset, _ = stage_export(
            s, parse_export("Contacts", data), data, "source-contact.csv"
        )
        row = s.scalar(
            select(StagingRow).where(StagingRow.staging_dataset_id == dataset.id)
        )
        source = CRMContact(
            airtable_id="source-contact", label="Supplier contact", source_row_id=row.id
        )
        invalid = CRMContact(
            airtable_id="invalid", label="No email", profile={"email": ""}
        )
        s.add_all([source, invalid])
        s.flush()
        mah = CRMMah(
            name="Email test",
            contract_status="unknown",
            created_at=utcnow(),
            updated_at=utcnow(),
            profile={"spoc_ids": [invalid.id], "alert_contact_ids": [invalid.id]},
        )
        s.add(mah)
        s.commit()
        findings = check_integrity(s, 2025)["findings"]
        assert any(
            f["rule"] == "contact_source_only" and f["id"] == source.id
            for f in findings
        )
        assert not any(
            f["rule"] == "contact_orphan" and f["id"] == source.id for f in findings
        )
        assert any(
            f["rule"] == "contact_email"
            and f["id"] == invalid.id
            and f["severity"] == "Review"
            for f in findings
        )
        assert not any(
            f["rule"] in ("mah_spoc", "mah_alert_manager") and f["id"] == mah.id
            for f in findings
        )
