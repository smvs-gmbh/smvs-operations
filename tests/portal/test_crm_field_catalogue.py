from datetime import date

from sqlalchemy import select

from app.domain.crm.imports import parse_export, stage_export
from app.domain.crm.mahs import seed_staged_mahs
from app.domain.models import CRMAgreement, CRMContact, CRMMah
from app.portal.crm_field_catalogue import CATALOGUE, DEFAULT_COLUMNS, catalogue_context
from app.portal.crm_routes import router


def test_catalogue_preserves_current_values_and_resolves_agreements(portal):
    client, factory = portal
    client.app.include_router(router)
    content = (
        b"RECORD_ID,MAH Name,Street,Phone,Company summary,Contract Status (from Agreements),Signing Date (from Contract),Email general\n"
        b"rec1,Example MAH,Imported street,012345,Imported summary,Terminated,01.01.2020,info@example.test\n"
    )
    with factory.begin() as session:
        stage_export(session, parse_export("MAH", content), content, "mah.csv")
        seed_staged_mahs(session)
        mah = session.scalar(select(CRMMah))
        mah.profile = (mah.profile or {}) | {"street": "Maintained street", "phone": ""}
        session.add(
            CRMAgreement(
                contract_id="CURRENT",
                contractor="Example MAH",
                status="Signed",
                signing_date=date(2026, 5, 1),
                mahs=[mah],
            )
        )
        session.flush()
        values = catalogue_context(session, "mahs", [mah])["crm_field_cells"][mah.id]
        assert values["street"] == "Maintained street"
        assert values["phone"] == "—"
        assert values["source_email_general"] == "info@example.test"
        assert values["contract"] == "Signed"
        assert values["signing_date"] == "2026-05-01"
        assert values["agreement_count"] == "1"
    page = client.get("/crm/mahs").text
    assert 'data-column="street" data-default-visible="false" hidden' in page
    assert "Maintained street" in page
    assert "Email general · imported" in page
    assert 'data-column="source_signing_date_from_contract"' not in page


def test_all_crm_catalogues_render_and_contact_values_are_escaped(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory.begin() as session:
        session.add(
            CRMContact(
                airtable_id="contact1",
                label="Example contact",
                profile={
                    "email": "person@example.test",
                    "phone": "<script>alert(1)</script>",
                },
            )
        )
    for view, fields in CATALOGUE.items():
        keys = [field.key for field in fields]
        assert len(keys) == len(set(keys))
        assert set(DEFAULT_COLUMNS[view]).issubset(keys)
        assert all(field.operators for field in fields)
        assert not any("auth_code" in key or "record_id" in key for key in keys)
        response = client.get("/crm/" + view)
        assert response.status_code == 200, view
        for field in fields:
            assert f'data-column="{field.key}"' in response.text
    contacts = client.get("/crm/contacts").text
    assert "person@example.test" in contacts
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in contacts
    assert "<script>alert(1)</script>" not in contacts


def test_portal_stylesheet_is_served_as_css(portal):
    client, _ = portal
    response = client.get("/portal-static/portal.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert response.text.startswith(":root{")
    assert "<!doctype" not in response.text.lower()
