import re

from sqlalchemy import select

from app.domain.crm.contacts import seed_staged_contacts
from app.domain.crm.end_users import seed_end_users
from app.domain.crm.imports import parse_export, stage_export
from app.domain.crm.mahs import seed_staged_mahs
from app.domain.models import (
    CRMContact,
    CRMEndUser,
    CRMMah,
    LocalOrganisation,
    ParticipantMappingRun,
    ParticipantPublication,
)
from app.integration.artifacts.storage import utcnow
from app.portal.crm_routes import router

ORIGIN = {"origin": "http://testserver"}


def test_mah_import_edit_archive_restore_and_create(portal, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.portal.crm_routes.get_settings",
        lambda: SimpleNamespace(logo_dev_publishable_key="pk_test"),
    )
    client, factory = portal
    client.app.include_router(router)
    data = (
        b"RECORD_ID,MAH Name,Record Id,GLN,UID,Checked,Contract Status (from Agreements),Street,Email invoice,Payment Platform,Signing Date (from Contract),Association,Eligible for invoicing,Domain,Industry\n"
        b'rec1,Example Holder,Holder link,01234,CHE-123,checked,Signed,Test Street,billing@example.test,checked,1.2.2026,"interpharma,scienceindustries",checked,example.test,Pharma\n'
    )
    with factory() as session:
        stage_export(session, parse_export("MAH", data), data, "mah.csv")
        assert seed_staged_mahs(session) == 1
        session.commit()
        record = session.scalar(select(CRMMah))
        identifier, version = record.id, str(record.version)
        assert record.gln == "01234"
        assert record.registration_checked == 1 and record.contract_status == "unknown"
    url = f"/crm/mahs/{identifier}"
    overview = client.get(url).text
    assert 'aria-label="Edit general"' in overview and "Test Street" in overview
    assert 'name="street"' not in overview
    detail = client.get(url + "?edit=general").text
    address = client.get(url + "?edit=address").text
    invoice = client.get(url + "?edit=invoice").text
    contract = client.get(url + "?edit=contract").text
    assert 'name="street"' not in detail and 'name="name"' not in address
    assert "Cancel" in detail
    assert "Signed" in detail
    assert 'name="association:interpharma" value="yes" checked' in detail
    assert 'name="association:scienceindustries" value="yes" checked' in detail
    assert 'name="eligible_for_invoicing" value="yes" checked' in invoice
    assert "https://img.logo.dev/example.test?token=pk_test" in detail
    assert (
        "<td>Industry</td><td>1</td><td>0</td><td>Original export only</td>"
        in client.get("/crm/imports").text
    )
    assert 'value="Test Street"' in address
    assert 'value="2026-02-01"' in contract
    assert invoice.count('name="invoice_email"') == 1
    assert 'name="payment_platform" value="yes" checked' in invoice
    assert (
        client.post(
            url,
            data={
                "command": "save",
                "section": "address",
                "version": version,
                "street": "Updated Street",
                "contract_status": "active",
                "invoice_email": "outside@example.test",
            },
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    with factory() as session:
        record = session.get(CRMMah, identifier)
        assert record.profile == {"street": "Updated Street"}
        assert record.contract_status == "unknown"
        version = str(record.version)
    contact_csv = (
        b"RECORD_ID2,Record Id,Function,Link MAH\n"
        b'recContact,contact@example.test,"Alert liaison,SPOC",Holder link\n'
    )
    with factory() as session:
        stage_export(
            session, parse_export("Contacts", contact_csv), contact_csv, "contacts.csv"
        )
        assert seed_staged_contacts(session) == 1
        session.commit()
        assert seed_staged_contacts(session) == 0
        contact_id = session.scalar(select(CRMContact.id))
    assert "contact@example.test" in client.get("/crm/contacts").text
    assert "contact@example.test" in client.get(url + "?edit=contacts").text
    contact_url = f"/crm/contacts/{contact_id}"
    profile_page = client.get(contact_url).text
    assert (
        "Airtable organisation link" in profile_page
        and "Example Holder" in profile_page
    )
    assert "contact@example.test" in profile_page
    assert (
        client.post(
            contact_url,
            data={
                "section": "general",
                "version": "1",
                "first_name": "Ada",
                "last_name": "Example",
                "address_type": "work",
                "function:Alert liaison": "yes",
                "function:SPOC": "yes",
            },
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            contact_url,
            data={
                "section": "communication",
                "version": "2",
                "email": "new@example.test",
                "phone": "1234",
            },
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert "Ada Example" in client.get("/crm/contacts?q=Ada").text
    assert "new@example.test" in client.get(contact_url).text
    full_export = (
        b"RECORD_ID2,Record Id,Function,Link MAH,First Name,Email,Mailbox Type\n"
        b"recContact,contact@example.test,SPOC,Holder link,Imported,source@example.test,Shared Mailbox\n"
    )
    with factory() as session:
        stage_export(
            session, parse_export("Contacts", full_export), full_export, "full.csv"
        )
        assert seed_staged_contacts(session) == 1
        session.commit()
        assert seed_staged_contacts(session) == 0
        contact = session.get(CRMContact, contact_id)
        assert contact.profile["email"] == "new@example.test"
        assert contact.profile["first_name"] == "Ada"
        assert contact.profile["mailbox_type"] == "Shared Mailbox"
    assert "Shared Mailbox" in client.get(contact_url).text
    assignment = {
        "command": "save",
        "section": "contacts",
        "version": version,
        "spoc_id": contact_id,
        "alert_contact_ids": str(contact_id),
    }
    assert (
        client.post(
            url, data={**assignment, "spoc_id": 9999}, headers=ORIGIN
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, data=assignment, headers=ORIGIN, follow_redirects=False
        ).status_code
        == 303
    )
    assert "Ada Example" in client.get(url).text
    with factory() as session:
        record = session.get(CRMMah, identifier)
        assert record.profile["spoc_id"] == contact_id
        assert record.profile["alert_contact_ids"] == [contact_id]
        assert record.profile["street"] == "Updated Street"
        version = str(record.version)
    fields = {
        "name": "Edited Holder",
        "gln": "01234",
        "uid": "CHE-123",
        "registration_checked": "yes",
        "contract_status": "active",
    }
    edit = {
        "command": "save",
        "version": version,
        "edit_profile": "yes",
        "invoice_email": "updated@example.test",
        "associations_present": "yes",
        "association:scienceindustries": "yes",
        "invoice_routing_present": "yes",
        "street": "",
        **fields,
    }
    assert (
        client.post(
            url, data={**edit, "parent_company_id": identifier}, headers=ORIGIN
        ).status_code
        == 422
    )
    assert client.post(url, data=edit).status_code == 403
    assert (
        client.post(url, data=edit, headers=ORIGIN, follow_redirects=False).status_code
        == 303
    )
    assert client.post(url, data=edit, headers=ORIGIN).status_code == 409
    with factory() as session:
        assert seed_staged_mahs(session) == 0
        record = session.get(CRMMah, identifier)
        assert record.name == "Edited Holder" and record.contract_status == "active"
        assert record.profile["invoice_email"] == "updated@example.test"
        assert record.profile["street"] == ""
        assert record.profile["payment_platform"] is False
        assert record.profile["eligible_for_invoicing"] is False
        assert record.profile["associations"] == ["scienceindustries"]
        version = str(record.version)
    assert (
        client.post(
            url,
            data={"command": "archive", "version": version},
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert "Edited Holder" not in client.get("/crm/mahs").text
    assert "Edited Holder" in client.get("/crm/mahs?archived=true").text
    with factory() as session:
        version = str(session.get(CRMMah, identifier).version)
    assert (
        client.post(
            url,
            data={"command": "restore", "version": version},
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert "Edited Holder" in client.get("/crm/mahs").text
    assert (
        client.post(
            "/crm/mahs",
            data={**fields, "name": "New Holder", "parent_company_id": identifier},
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert "New Holder" in client.get("/crm/mahs?q=New").text
    with factory() as session:
        child = session.scalar(select(CRMMah).where(CRMMah.name == "New Holder"))
        assert child.parent_company_id == identifier
        child_id = child.id
        assert "(parent company)" in client.get(f"/crm/mahs/{child_id}").text
        version = str(session.get(CRMMah, identifier).version)
    assert (
        client.post(
            url,
            data={**edit, "version": version, "parent_company_id": child_id},
            headers=ORIGIN,
        ).status_code
        == 422
    )


def test_end_user_import_review_filters_and_marks_rows(portal):
    client, factory = portal
    client.app.include_router(router)
    content = b"Record Id,End User Name,Software Product\nAlpha,Alpha,Software A\nBeta,Beta,\n"
    with factory() as session:
        staged, _ = stage_export(
            session, parse_export("End Users", content), content, "end-users.csv"
        )
        now = utcnow()
        run = ParticipantMappingRun(
            input_key="test",
            snapshot_run_id=staged.processing_run_id,
            source_namespace="test",
            mapping_version="1",
            status="succeeded",
            started_at=now,
        )
        session.add(run)
        session.flush()
        orgs = [
            LocalOrganisation(
                source_key=name,
                source_namespace="test",
                source_organisation_id=name,
                organisation_name=name,
                is_observed=1,
                last_participant_run_id=run.id,
                evidence={},
            )
            for name in ("Alpha", "Beta NMVS")
        ]
        session.add_all(orgs)
        session.add(
            ParticipantPublication(
                name="participants",
                mapping_run_id=run.id,
                source_namespace="test",
                snapshot_date=now.date(),
                published_at=now,
            )
        )
        session.flush()
        assert seed_end_users(session) == (2, 1)
        session.commit()
        assert seed_end_users(session) == (0, 0)
        beta = session.scalar(select(CRMEndUser).where(CRMEndUser.name == "Beta"))
        beta_id = beta.id
        org_id = orgs[1].id
    detail = f"/crm/end-users/{beta_id}"
    overview = client.get(detail).text
    assert "Link organisation" in overview
    assert 'rel="prev"' in overview and 'rel="next"' not in overview
    filtered = client.get(detail + "?unlinked=true&q=Beta").text
    assert 'rel="prev"' not in filtered and 'rel="next"' not in filtered
    assert 'href="/crm/end-users?q=Beta&amp;unlinked=true"' in filtered
    assert "Beta NMVS" in client.get(detail + "?edit=true").text
    response = client.post(
        detail + "/organisation",
        data={
            "organisation_id": org_id,
            "previous_organisation_id": "",
        },
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "Manual assignment" in client.get(detail).text
    assert "No matching End Users." in client.get("/crm/end-users?unlinked=true").text
    url = "/crm/imports"
    page = client.get(url + "?q=software+a").text
    assert "Reviewed: Alpha" in page and "Reviewed: Beta" not in page
    action = re.search(r'action="(/crm/imports/end-users/\d+/review)"', page)[1]
    assert (
        client.post(
            action, data={"reviewed": "yes"}, headers=ORIGIN, follow_redirects=False
        ).status_code
        == 303
    )
    assert 'aria-label="Reviewed: Alpha" checked' in client.get(url).text
    assert "Reviewed: Alpha" not in client.get(url + "?pending_only=true").text
    assert (
        client.post(
            action, data={"q": ""}, headers=ORIGIN, follow_redirects=False
        ).status_code
        == 303
    )
    assert "Reviewed: Alpha" in client.get(url + "?pending_only=true").text
    assert "Create End User" in client.get("/crm/end-users/new").text
    created = client.post(
        "/crm/end-users",
        data={"name": "Manual Pharmacy"},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert created.status_code == 303
    manual_url = created.headers["location"]
    with factory() as session:
        contact = CRMContact(airtable_id="test-contact", label="Test Contact")
        session.add(contact)
        session.commit()
        contact_id = contact.id
        assert seed_end_users(session) == (0, 0)
    assert "Test Contact" in client.get(manual_url + "?edit=contacts").text

    def save(version, command, **fields):
        return client.post(
            manual_url,
            data={"version": version, "command": command, **fields},
            headers=ORIGIN,
            follow_redirects=False,
        )

    assert (
        save(
            "1", "general", name="Renamed Pharmacy", software="Sample Software"
        ).status_code
        == 303
    )
    assert save("1", "general", name="Stale").status_code == 409
    assert (
        save(
            "2", "contacts", spoc_id=contact_id, alert_contact_ids=str(contact_id)
        ).status_code
        == 303
    )
    assert "Test Contact" in client.get(manual_url).text
    assert "Renamed Pharmacy" in client.get(f"/crm/contacts/{contact_id}").text
    assert save("3", "archive").status_code == 303
    assert "Renamed Pharmacy" not in client.get("/crm/end-users").text
    assert "Renamed Pharmacy" in client.get("/crm/end-users?archived=true").text
    assert save("4", "restore").status_code == 303
    assert "Test Contact" in client.get(manual_url).text


def test_end_user_contact_backfill_preserves_manual_choices(portal):
    _, factory = portal
    from app.domain.crm.end_users import seed_end_user_contacts

    content = (
        b"Record Id,End User Name,SPOC,Alert contacts\n"
        b'Alpha,Alpha,recA,"Unique,Duplicate"\n'
        b'Beta,Beta,"Unique,recA",Unique\n'
    )
    with factory() as session:
        stage_export(
            session, parse_export("End Users", content), content, "end-users.csv"
        )
        session.add_all(
            [
                CRMContact(airtable_id="recA", label="Unique"),
                CRMContact(airtable_id="recB", label="Duplicate"),
                CRMContact(airtable_id="recC", label="Duplicate"),
            ]
        )
        assert seed_end_users(session) == (2, 0)
        alpha, beta = session.scalars(
            select(CRMEndUser).order_by(CRMEndUser.name)
        ).all()
        alpha.profile = {"spoc_id": None}
        unique = session.scalar(
            select(CRMContact.id).where(CRMContact.airtable_id == "recA")
        )
        assert seed_end_user_contacts(session) == {"alert_contact_ids": 2}
        session.commit()
        assert alpha.profile == {"spoc_id": None, "alert_contact_ids": [unique]}
        assert beta.profile == {"alert_contact_ids": [unique]}
        assert not seed_end_user_contacts(session)
