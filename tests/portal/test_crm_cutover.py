# ruff: noqa: F811 -- shared portal fixture

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.db.models import StagingRow
from app.domain.crm.imports import parse_export, stage_export
from app.domain.crm.organisation_links import (
    affiliations,
    migrate_affiliations,
    set_affiliations,
)
from app.domain.models import (
    CRMContact,
    CRMContactLinkEvent,
    CRMContactOrganisationLink,
    CRMEndUser,
    CRMITSupplierIdentity,
    CRMMah,
)
from app.integration.artifacts.storage import utcnow
from app.portal.crm_field_catalogue import CATALOGUE, catalogue_context
from tests.portal.test_crm_views import post_view, views_portal  # noqa: F401


def seed_links(factory):
    with factory.begin() as session:
        mah_csv = b"RECORD_ID,Record Id,MAH Name\nm1,Holder source,Holder\n"
        contact_csv = b"RECORD_ID2,Record Id,Function,Link MAH,Link End Users,Link IT Supplier\nc1,Contact source,SPOC,Holder source,User source,Supplier source\n"
        user_csv = b"Record Id,End User Name\nUser source,User\n"
        supplier_csv = b"Record Id,IT Supplier Name\nSupplier source,Supplier\n"
        rows = {}
        for table, content in [
            ("MAH", mah_csv),
            ("Contacts", contact_csv),
            ("End Users", user_csv),
            ("IT Suppliers", supplier_csv),
        ]:
            dataset, _ = stage_export(
                session, parse_export(table, content), content, "synthetic.csv"
            )
            rows[table] = session.scalar(
                select(StagingRow).where(StagingRow.staging_dataset_id == dataset.id)
            )
        mah = CRMMah(
            airtable_id="m1",
            name="Holder",
            contract_status="unknown",
            created_at=utcnow(),
            updated_at=utcnow(),
            source_row_id=rows["MAH"].id,
        )
        user = CRMEndUser(name="User", source_row_id=rows["End Users"].id)
        contact = CRMContact(
            airtable_id="c1",
            label="Person",
            function="SPOC",
            source_row_id=rows["Contacts"].id,
        )
        session.add_all([mah, user, contact])
        session.flush()
        return mah.id, user.id, contact.id


def test_migration_unifies_affiliations_without_granting_roles_and_is_idempotent(
    views_portal,
):
    client, factory = views_portal
    mid, _uid, cid = seed_links(factory)
    with factory.begin() as session:
        before = session.scalar(
            select(func.count()).select_from(CRMContactOrganisationLink)
        )
        plan = migrate_affiliations(session)
        assert plan["new_links"] == 3 and not plan["unresolved"]
        assert (
            session.scalar(select(func.count()).select_from(CRMContactOrganisationLink))
            == before
        )
        assert migrate_affiliations(session, apply=True)["new_links"] == 3
        session.flush()
        assert migrate_affiliations(session, apply=True)["new_links"] == 0
        assert (
            session.scalar(select(func.count()).select_from(CRMContactLinkEvent)) == 3
        )
        links = affiliations(session, {cid})[cid]
        assert {v["type"] for v in links} == {"MAH", "End User", "IT Supplier"}
        assert all(
            v["roles"] == ["Contact"] for v in links
        )  # Global Function=SPOC is not an organisation role.
        assert not (session.get(CRMMah, mid).profile or {}).get("spoc_ids")
        parent = catalogue_context(session, "mahs", [session.get(CRMMah, mid)])["crm_field_values"][mid]
        assert parent["contacts"] == ["Person"] and parent["spocs"] == []
        cells = catalogue_context(session, "contacts", [session.get(CRMContact, cid)])[
            "crm_field_cells"
        ][cid]
        assert all(
            label in cells["assigned_organisations"]
            for label in ("Holder", "User", "Supplier")
        )
        session.get(CRMMah, mid).profile = {"spoc_ids": [cid]}
        assert next(v for v in affiliations(session, {cid})[cid] if v["kind"] == "mah")[
            "roles"
        ] == ["SPOC"]
    detail = client.get(f"/crm/contacts/{cid}")
    assert detail.status_code == 200 and "Assigned MAHs" not in detail.text
    assert (
        "Holder" in detail.text and "Supplier" in detail.text and "Roles" in detail.text
    )
    page = client.get("/crm/contacts").text
    assert "Assigned organisations" in page and "Link MAH" not in page


def test_manual_unassignment_survives_reimport_and_target_fk_constraints(views_portal):
    _client, factory = views_portal
    mid, uid, cid = seed_links(factory)
    with factory.begin() as session:
        migrate_affiliations(session, apply=True)
        session.flush()
        contact = session.get(CRMContact, cid)
        supplier = session.scalar(select(CRMITSupplierIdentity))
        set_affiliations(session, contact, [f"mah:{mid}"])
        session.flush()
        assert len(affiliations(session, {cid})[cid]) == 1
        assert migrate_affiliations(session, apply=True)["new_links"] == 0
        assert len(affiliations(session, {cid})[cid]) == 1
        original_id = supplier.id
        new = b"Record Id,IT Supplier Name\nSupplier source,Renamed supplier\n"
        stage_export(session, parse_export("IT Suppliers", new), new, "updated.csv")
        assert session.scalar(select(CRMITSupplierIdentity.id)) == original_id
        assert not any(
            v["kind"] == "supplier" for v in affiliations(session, {cid})[cid]
        )
        session.get(CRMMah, mid).profile = {"spoc_ids": [cid]}
        set_affiliations(session, contact, [])
        assert affiliations(session, {cid})[cid][0]["roles"] == ["SPOC"]
    with factory() as session:
        session.add(
            CRMContactOrganisationLink(
                contact_id=cid,
                mah_id=mid,
                end_user_id=uid,
                is_active=True,
                origin="manual",
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        session.add(
            CRMContactOrganisationLink(
                contact_id=999999,
                mah_id=mid,
                is_active=True,
                origin="manual",
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_affiliation_edit_uses_contact_version_and_does_not_remove_roles(views_portal):
    client, factory = views_portal
    mid, _uid, cid = seed_links(factory)
    with factory.begin() as session:
        migrate_affiliations(session, apply=True)
        session.get(CRMMah, mid).profile = {"spoc_ids": [cid]}
        version = session.get(CRMContact, cid).version
    response = client.post(
        f"/crm/contacts/{cid}",
        headers={"origin": "http://testserver", "x-test-user": "1"},
        data={"section": "organisations", "version": str(version)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with factory() as session:
        links = affiliations(session, {cid})[cid]
        assert (
            len(links) == 1
            and links[0]["kind"] == "mah"
            and links[0]["roles"] == ["SPOC"]
        )
        assert (
            session.scalar(select(func.count()).select_from(CRMContactLinkEvent)) >= 5
        )
    assert (
        client.post(
            f"/crm/contacts/{cid}",
            headers={"origin": "http://testserver"},
            data={"section": "organisations", "version": str(version)},
            follow_redirects=False,
        ).status_code
        == 409
    )


def test_removed_fields_are_not_selectable_but_saved_predicates_fail_closed(
    views_portal,
):
    client, factory = views_portal
    seed_links(factory)
    for directory, fields in CATALOGUE.items():
        keys = {f.key for f in fields}
        if directory == "agreements":
            assert not keys & {
                "source_notes",
                "source_tasks",
                "source_type",
                "source_created_by",
            }
        if directory == "mahs":
            assert not keys & {
                "source_logo",
                "source_tasks",
                "created_at",
                "updated_at",
                "archived_at",
            }
        if directory == "contacts":
            assert not keys & {
                "assigned_mahs",
                "source_link_mah",
                "source_link_it_supplier",
            }
    config = {
        "columns": ["name", "source_tasks"],
        "conditions": [{"field": "source_tasks", "operator": "empty", "value": ""}],
    }
    saved = post_view(client, command="create", name="Old task view", config=config)
    assert saved.status_code == 200
    view = saved.json()["view"]
    assert view["config"]["columns"] == ["name"] and view["config"][
        "retired_fields"
    ] == ["source_tasks"]
    page = client.get(
        "/crm/mahs", params={"view": view["id"]}, headers={"x-test-user": "1"}
    )
    assert page.status_code == 200 and "0 results" in page.text
    config["conditions"] = []
    assert (
        post_view(client, command="preview", config=config).json()["config"][
            "retired_fields"
        ]
        == []
    )


def test_end_user_reimport_preserves_identity_and_manual_crm_values(views_portal):
    from app.domain.crm.end_users import seed_end_users

    _, factory = views_portal
    first = b"Record Id,End User Name,Email general\nunique-source,Original,old@example.test\n"
    second = b"Record Id,End User Name,Email general\nunique-source,Source rename,new@example.test\n"
    with factory.begin() as session:
        stage_export(session, parse_export("End Users", first), first, "first.csv")
        assert seed_end_users(session)[0] == 1
        row = session.scalar(select(CRMEndUser))
        identifier = row.id
        row.name = "Operations name"
        row.profile = {"email": "manual@example.test"}
        session.flush()
        stage_export(session, parse_export("End Users", second), second, "second.csv")
        assert seed_end_users(session)[0] == 0
        assert session.scalar(select(func.count()).select_from(CRMEndUser)) == 1
        assert (
            row.id == identifier
            and row.name == "Operations name"
            and row.profile["email"] == "manual@example.test"
        )


def test_shared_logo_display_preserves_source_and_rejects_unsafe_urls():
    from app.domain.crm.logos import organisation_logo

    raw = {"Logo URL": "https://images.example.test/logo.png"}
    assert organisation_logo(raw, {}, None) == raw["Logo URL"]
    assert raw == {"Logo URL": "https://images.example.test/logo.png"}
    assert organisation_logo({"Logo URL": "javascript:alert(1)"}, {}, None) is None
    assert (
        organisation_logo(
            {"Logo URL": "https://user:password@example.test/x"}, {}, None
        )
        is None
    )
    assert organisation_logo({"Domain": None}, {}, None) is None


def test_legacy_assignment_display_columns_map_to_one_field_without_relaxing_predicates(
    views_portal,
):
    client, _ = views_portal
    config = {
        "columns": [
            "name",
            "assigned_mahs",
            "source_link_end_users",
            "source_link_it_supplier",
        ],
        "conditions": [{"field": "source_link_mah", "operator": "empty", "value": ""}],
    }
    response = post_view(client, "contacts", command="preview", config=config)
    assert response.status_code == 200
    result = response.json()["config"]
    assert result["columns"] == ["name", "assigned_organisations"]
    assert result["retired_fields"] == ["source_link_mah"]
