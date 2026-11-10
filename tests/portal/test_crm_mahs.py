import re
from types import SimpleNamespace

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
    assert '<details class="panel review-body mah-company-summary" >' in overview
    summary_form = client.get(url + "?edit=company-summary").text
    assert (
        '<details class="panel review-body mah-company-summary" open>' in summary_form
    )
    assert (
        'name="company_summary"' in summary_form
        and 'name="company_size"' in summary_form
    )
    assert 'name="gln"' not in summary_form
    detail = client.get(url + "?edit=general").text
    address = client.get(url + "?edit=address").text
    invoice = client.get(url + "?edit=invoice").text
    contract = client.get(url + "?edit=contract").text
    assert 'name="street"' not in detail and 'name="name"' not in address
    assert "Cancel" in detail
    assert "No linked agreement." in detail
    assert 'name="association:interpharma" value="yes" checked' in detail
    assert 'name="association:scienceindustries" value="yes" checked' in detail
    assert 'name="eligible_for_invoicing" value="yes" checked' in invoice
    assert "https://img.logo.dev/example.test?token=pk_test" in detail
    assert (
        "<td>Industry</td><td>1</td><td>0</td><td>Original export only</td>"
        in client.get("/crm/imports").text
    )
    assert 'value="Test Street"' in address
    assert 'name="signing_date"' not in contract
    assert "Imported signing date" not in contract
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
    summary_saved = client.post(
        url,
        data={
            "command": "save",
            "section": "company-summary",
            "version": version,
            "company_summary": "Updated summary",
            "company_size": "42",
            "gln": "ignored",
        },
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert summary_saved.status_code == 303
    assert summary_saved.headers["location"].endswith("?summary=open#company-summary")
    with factory() as session:
        record = session.get(CRMMah, identifier)
        assert record.profile["company_summary"] == "Updated summary"
        assert record.profile["company_size"] == "42"
        assert record.gln == "01234"
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
    with factory() as session:
        backup = CRMContact(airtable_id="recBackup", label="Backup Contact")
        session.add(backup)
        session.commit()
        backup_id = backup.id
    assert "Shared Mailbox" in client.get(contact_url).text
    assignment = {
        "command": "save",
        "section": "contacts",
        "version": version,
        "spoc_ids": f"{contact_id},{backup_id}",
        "alert_contact_ids": str(contact_id),
    }
    assert (
        client.post(
            url, data={**assignment, "spoc_ids": "9999"}, headers=ORIGIN
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
    assert "Backup Contact" in client.get(url).text
    assert "Example Holder" in client.get(f"/crm/contacts/{backup_id}").text
    with factory() as session:
        record = session.get(CRMMah, identifier)
        assert record.profile["spoc_ids"] == [contact_id, backup_id]
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
    picker = client.get(detail + "?edit=true").text
    assert "Beta NMVS" in picker
    assert "Search by organisation name or ID" in picker
    assert "data-organisation-picker" in picker
    assert "Published NMVS Snapshot:" in picker
    assert "organisation-picker.js" in picker
    assert 'name="organisation_id"' in picker
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
        b'Beta,Beta,"Unique,recB",Unique\n'
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
        assert seed_end_user_contacts(session) == {
            "spoc_ids": 1,
            "alert_contact_ids": 2,
        }
        session.commit()
        assert alpha.profile == {"spoc_id": None, "alert_contact_ids": [unique]}
        backup = session.scalar(
            select(CRMContact.id).where(CRMContact.airtable_id == "recB")
        )
        assert beta.profile == {
            "spoc_ids": [unique, backup],
            "alert_contact_ids": [unique],
        }
        assert not seed_end_user_contacts(session)


def test_agreement_review_filters_and_reversible_attachment_exclusion(portal):
    from app.core.db.models import AcquiredArtifact
    from app.domain.crm.agreements import archive_pdf, seed_agreements
    from app.domain.models import CRMAgreement

    client, factory = portal
    client.app.include_router(router)
    holders = (
        b"RECORD_ID,MAH Name,Agreements\n"
        b"recOne,Holder One,C-1\nrecTwo,Holder Two,C-2\nrecThree,Holder Three,C-2\n"
    )
    contracts = (
        b"Contract ID,Contractor,Status,Agreement,Signing Date\n"
        b"C-1,Holder One,Signed,,1.2.2026\nC-2,Original Contractor,Signed,,2.3.2026\n"
    )
    with factory() as s:
        stage_export(s, parse_export("MAH", holders), holders, "holders.csv")
        seed_staged_mahs(s)
        stage_export(
            s, parse_export("MAH Agreements", contracts), contracts, "contracts.csv"
        )
        assert seed_agreements(s) == 2
        assert archive_pdf(s, "C-2", "first.pdf", b"%PDF- first")
        assert archive_pdf(s, "C-2", "second.pdf", b"%PDF- second")
        s.commit()
        first, second = s.scalars(select(CRMAgreement).order_by(CRMAgreement.id)).all()
        assert first.mahs and not second.mahs
        holder = s.scalar(select(CRMMah).where(CRMMah.name == "Holder Two"))
        attachment = next(
            item
            for item in s.scalars(select(AcquiredArtifact))
            if item.report_metadata.get("filename") == "second.pdf"
        )
        identifier, mah_id, artifact_id = second.id, holder.id, attachment.id

    directory = "/crm/agreements"
    url = f"{directory}/{identifier}"
    assert "Original Contractor" in client.get(f"{directory}?link=ambiguous").text
    assert "Original Contractor" in client.get(f"{directory}?attachments=multiple").text
    assert (
        "Original Contractor" not in client.get(f"{directory}?attachments=missing").text
    )
    assert "Holder Two" in client.get("/crm/mahs?agreement=missing").text
    assert "second.pdf" in client.get(url).text
    assert client.get(f"{url}/pdf/{artifact_id}").status_code == 403
    assert (
        client.post(
            url, headers=ORIGIN, data={"command": "assign", "mah_id": mah_id}
        ).status_code
        == 200
    )
    assert "Holder Two" not in client.get("/crm/mahs?agreement=missing").text
    assert "Original Contractor" not in client.get(f"{directory}?link=ambiguous").text
    for command, expected in (("exclude", False), ("restore", True)):
        assert (
            client.post(
                url,
                headers=ORIGIN,
                data={"command": command, "artifact_id": artifact_id},
            ).status_code
            == 200
        )
        assert (
            "Original Contractor"
            in client.get(f"{directory}?attachments=multiple").text
        ) is expected
    mah_url = f"/crm/mahs/{mah_id}"
    mah_page = client.get(mah_url).text
    assert "<td>Signed</td><td>2026-03-02</td>" in mah_page
    heading = mah_page.split('data-mah-card="contract"', 1)[1].split("</div>", 1)[0]
    assert "Manage agreements" in heading
    assert 'aria-label="Edit agreement C-2"' in mah_page
    assert (
        client.post(
            url,
            headers=ORIGIN,
            data={
                "command": "details",
                "status": "Terminated",
                "signing_date": "2026-03-03",
            },
        ).status_code
        == 200
    )
    assert "<td>Terminated</td><td>2026-03-03</td>" in client.get(mah_url).text
    assert "Holder Two" in client.get("/crm/mahs?agreement=no-signed").text
    editor = client.get(f"{mah_url}?edit=contract&agreement_id={identifier}").text
    assert 'name="signing_date" aria-label="Signing date" value="2026-03-03"' in editor
    with factory() as s:
        version = s.get(CRMMah, mah_id).version
        unrelated_id = s.scalar(
            select(CRMAgreement.id).where(~CRMAgreement.mahs.any(CRMMah.id == mah_id))
        )
    details = {
        "command": "save",
        "section": "contract",
        "version": version,
        "status": "Signed",
        "signing_date": "2026-03-04",
    }
    assert (
        client.post(
            mah_url, headers=ORIGIN, data={**details, "agreement_id": unrelated_id}
        ).status_code
        == 409
    )
    assert (
        client.post(
            mah_url, headers=ORIGIN, data={**details, "agreement_id": identifier}
        ).status_code
        == 200
    )
    assert 'value="2026-03-04"' in client.get(url).text
    editor = client.get(f"{mah_url}?edit=contract-links").text
    assert f'name="agreement:{unrelated_id}"' in editor
    with factory() as s:
        version = s.get(CRMMah, mah_id).version
        other_mah_id = s.get(CRMAgreement, unrelated_id).mahs[0].id
    response = client.post(
        mah_url,
        headers=ORIGIN,
        data={
            "command": "save",
            "section": "contract-links",
            "version": version,
            f"agreement:{unrelated_id}": "yes",
            f"agreement:{identifier}": "yes",
        },
    )
    assert response.status_code == 200
    assert "C-1 →" in response.text and "C-2 →" in response.text
    first_url = f"{directory}/{unrelated_id}"
    response = client.post(
        first_url,
        headers=ORIGIN,
        data={
            "command": "assign",
            f"mah:{mah_id}": "yes",
            f"mah:{other_mah_id}": "yes",
        },
    )
    assert response.status_code == 200
    assert f'name="mah:{mah_id}" value="yes" checked' in response.text
    assert f'name="mah:{other_mah_id}" value="yes" checked' in response.text
    with factory() as s:
        assert {mah.id for mah in s.get(CRMAgreement, unrelated_id).mahs} == {
            mah_id,
            other_mah_id,
        }
    with factory() as s:
        assert seed_agreements(s) == 0
        assert {mah.id for mah in s.get(CRMAgreement, identifier).mahs} == {mah_id}


def test_mah_transfer_records_note_and_allows_separate_archiving(portal):
    from app.domain.models import CRMAgreement, CRMMahTransfer

    client, factory = portal
    client.app.include_router(router)
    holders = b"RECORD_ID,MAH Name\nrecFrom,Source Holder\nrecTo,Target Holder\n"
    with factory() as s:
        stage_export(s, parse_export("MAH", holders), holders, "holders.csv")
        seed_staged_mahs(s)
        s.commit()
        source, target = s.scalars(select(CRMMah).order_by(CRMMah.name)).all()
        source_id, target_id, version = source.id, target.id, source.version
        original = CRMAgreement(
            contract_id="C-Original",
            contractor=source.name,
            status="Signed",
            mahs=[source],
        )
        shared = CRMAgreement(
            contract_id="C-Shared",
            contractor=target.name,
            status="Signed",
            mahs=[source, target],
        )
        s.add_all([original, shared])
        s.commit()
        original_id, shared_id = original.id, shared.id

    source_url = f"/crm/mahs/{source_id}"
    target_url = f"/crm/mahs/{target_id}"
    assert (
        '<details class="exception-actions">\n<summary><strong>Actions</strong>'
        in client.get(source_url).text
    )
    page = client.get(source_url).text
    assert f'name="transfer_agreement:{original_id}" value="yes" checked' in page
    assert f'name="transfer_agreement:{shared_id}" value="yes" checked' not in page
    form = {
        "target_mah_id": target_id,
        "version": version,
        "note": "Transfer following acquisition",
        f"transfer_agreement:{original_id}": "yes",
    }
    assert (
        client.post(
            f"{source_url}/transfer",
            headers=ORIGIN,
            data={**form, "target_mah_id": source_id},
        ).status_code
        == 422
    )
    for _ in range(2):
        result = client.post(
            f"{source_url}/transfer", headers=ORIGIN, data=form, follow_redirects=False
        )
        assert (
            result.status_code == 303
            and result.headers["location"] == f"{target_url}#transfers"
        )
    assert "Transfer following acquisition" in client.get(target_url).text
    assert "Transferred" in client.get(source_url).text
    with factory() as s:
        source = s.get(CRMMah, source_id)
        assert source.profile["status"] == "Transferred" and source.archived_at is None
        assert s.scalars(select(CRMMahTransfer)).one().target_mah_id == target_id
        assert s.get(CRMAgreement, original_id).status == "Transferred"
        assert s.get(CRMAgreement, shared_id).status == "Signed"
        version = source.version
    assert (
        client.post(
            source_url, headers=ORIGIN, data={"command": "archive", "version": version}
        ).status_code
        == 200
    )
    assert "Transfer following acquisition" in client.get(target_url).text


def test_create_agreement_and_attach_pdf(portal):
    client, factory = portal
    client.app.include_router(router)

    from fastapi.testclient import TestClient

    async def signed_in(scope, receive, send):
        scope.setdefault("state", {})["portal_user"] = SimpleNamespace(id=0)
        await client.app(scope, receive, send)

    authenticated = TestClient(signed_in)

    holders = b"RECORD_ID,MAH Name\nrecExample,Example Holder\n"
    with factory() as s:
        stage_export(s, parse_export("MAH", holders), holders, "holders.csv")
        seed_staged_mahs(s)
        s.commit()
        mah_id = s.scalar(select(CRMMah.id))
    assert "New agreement" in client.get("/crm/agreements").text
    assert (
        f'value="{mah_id}" selected'
        in client.get(f"/crm/agreements/new?mah_id={mah_id}").text
    )
    fields = {
        "contract_id": "TEST-C-1",
        "status": "Signed",
        "mah_id": mah_id,
        "signing_date": "2026-11-06",
    }
    result = client.post(
        "/crm/agreements", headers=ORIGIN, data=fields, follow_redirects=False
    )
    assert result.status_code == 303
    url = result.headers["location"]
    assert "TEST-C-1" in client.get(f"/crm/mahs/{mah_id}").text
    assert (
        client.post("/crm/agreements", headers=ORIGIN, data=fields).status_code == 409
    )

    headers = {**ORIGIN, "x-filename": "agreement.pdf"}
    pdf = b"%PDF-1.7 synthetic test document"
    assert client.post(f"{url}/pdf", headers=ORIGIN, content=pdf).status_code == 403
    assert (
        authenticated.post(
            f"{url}/pdf", headers=headers, content=b"invalid"
        ).status_code
        == 422
    )
    for _ in range(2):
        assert (
            authenticated.post(f"{url}/pdf", headers=headers, content=pdf).status_code
            == 204
        )
    page = authenticated.get(url)
    assert page.text.count("agreement.pdf") == 1
    download = re.search(r'href="(' + url + r'/pdf/\d+)"', page.text)
    assert download
    assert authenticated.get(download[1]).content == pdf


def test_self_declaration_import_retains_conflicts_and_is_repeatable(portal):
    from app.domain.crm.self_declarations import seed_self_declarations
    from app.domain.models import CRMSelfDeclaration

    client, factory = portal
    client.app.include_router(router)
    holders = b"RECORD_ID,MAH Name,Selfdeclarations\nrecHolder,Current Holder,Old Holder 2025\n"
    data = (
        b"Record Id,Declaration year,MAH Name,RX packs sold,Sales related amount\n"
        b'Old Holder 2025,2025,Old Holder,120,"1000,00"\n'
        b'Old Holder 2025,2025,Old Holder,130,"1000,00"\n'
        b"Unknown 2024,2024,Unknown,,\n"
    )
    with factory() as s:
        stage_export(s, parse_export("MAH", holders), holders, "holders.csv")
        seed_staged_mahs(s)
        staged, _ = stage_export(
            s, parse_export("Self-declarations", data), data, "declarations.csv"
        )
        assert seed_self_declarations(s, staged.id) == 3
        s.commit()
        assert seed_self_declarations(s, staged.id) == 0
        mah_id = s.scalar(select(CRMMah.id))
        item = s.scalar(
            select(CRMSelfDeclaration).where(CRMSelfDeclaration.packs_sold == 120)
        )
        identifier = item.id
        assert item.mah_id == mah_id
    response = client.get("/crm/self-declarations?year=&duplicates=true")
    assert response.status_code == 200
    assert response.text.count("Repeated source label</small>") == 2
    assert (
        "Unknown 2024"
        in client.get("/crm/self-declarations?assignment=unassigned").text
    )
    assert "Self-declarations (2)" in client.get(f"/crm/mahs/{mah_id}").text
    detail = client.get(f"/crm/self-declarations/{identifier}?year=2025")
    assert detail.status_code == 200 and "1000,00" in detail.text


def test_archived_contact_is_restorable_and_unavailable_for_new_assignments(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory() as s:
        person = CRMContact(airtable_id="recArchive", label="Contact for archiving")
        holder = CRMMah(
            name="Holder",
            contract_status="unknown",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        s.add_all([person, holder])
        s.commit()
        contact_id, holder_id, version = person.id, holder.id, person.version
    url = f"/crm/contacts/{contact_id}"
    assert "Archive contact" in client.get(url).text
    assert (
        client.post(
            url, headers=ORIGIN, data={"command": "archive", "version": version}
        ).status_code
        == 200
    )
    assert "Contact for archiving" not in client.get("/crm/contacts").text
    assert "Contact for archiving" in client.get("/crm/contacts?archived=true").text
    mah_url = f"/crm/mahs/{holder_id}"
    assert "Contact for archiving" not in client.get(f"{mah_url}?edit=contacts").text
    form = {
        "command": "save",
        "section": "contacts",
        "version": 1,
        "spoc_ids": contact_id,
    }
    assert client.post(mah_url, headers=ORIGIN, data=form).status_code == 422
    with factory() as s:
        version = s.get(CRMContact, contact_id).version
    assert (
        client.post(
            url, headers=ORIGIN, data={"command": "restore", "version": version}
        ).status_code
        == 200
    )
    assert client.post(mah_url, headers=ORIGIN, data=form).status_code == 200


def test_mah_direct_search_uses_name_or_gln_and_eligibility_is_identifiable(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory.begin() as session:
        mah = CRMMah(
            name="Searchable holder",
            gln="7601234567890",
            uid="CHE-UNIQUE-UID",
            contract_status="unknown",
            created_at=utcnow(),
            updated_at=utcnow(),
            profile={"eligible_for_invoicing": True},
        )
        session.add(mah)
        session.flush()
        identifier = mah.id
    for query in ("Searchable", "7601234567890"):
        assert (
            ">Searchable holder</span>"
            in client.get("/crm/mahs", params={"q": query}).text
        )
    assert (
        ">Searchable holder</span>"
        not in client.get("/crm/mahs", params={"q": "CHE-UNIQUE-UID"}).text
    )
    page = client.get("/crm/mahs").text
    controls = page.split('<div class="review-controls">', 1)[1].split("</div>", 1)[0]
    assert "Name or GLN" in controls
    assert 'name="agreement"' not in controls and 'name="archived"' not in controls
    # Relationship and archive scopes remain available to saved views.
    assert "data-crm-view-filters" in page
    assert 'name="agreement"' in page and 'name="archived"' in page
    assert "Eligible for invoice" in page
    detail = client.get(f"/crm/mahs/{identifier}?edit=invoice").text
    assert "Eligible for invoice" in detail
    assert 'name="eligible_for_invoicing" value="yes" checked' in detail


def test_mah_edit_keeps_neighbour_controls_visible_and_save_restores_them(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory.begin() as session:
        for name in ("Alpha", "Beta", "Gamma"):
            session.add(
                CRMMah(
                    name=name,
                    contract_status="unknown",
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
        session.flush()
        record = session.scalar(select(CRMMah).where(CRMMah.name == "Beta"))
        identifier, version = record.id, record.version
    url = f"/crm/mahs/{identifier}"
    editor = client.get(url + "?edit=general").text
    nav = editor.split('<nav class="record-navigation"', 1)[1].split("</nav>", 1)[0]
    assert 'class="record-navigation-steps"' in nav
    assert 'data-record-editing="true"' in nav
    assert "← Previous" in nav and "Next →" in nav
    assert nav.count('aria-disabled="true"') == 2
    assert 'class="record-navigation-steps" hidden' not in nav
    result = client.post(
        url,
        headers=ORIGIN,
        data={
            "command": "save",
            "section": "general",
            "version": str(version),
            "name": "Beta reviewed",
            "registration_checked": "yes",
        },
    )
    assert result.status_code == 200
    nav = result.text.split('<nav class="record-navigation"', 1)[1].split("</nav>", 1)[
        0
    ]
    assert 'data-record-editing="false"' in nav
    assert re.search(r'rel="prev"[^>]* href=', nav)
    assert re.search(r'rel="next"[^>]* href=', nav)


def test_create_contact_from_directory_then_edit_and_archive(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory.begin() as session:
        session.add(
            CRMContact(airtable_id="known-role", label="Existing", function="SPOC")
        )
    listing = client.get("/crm/contacts").text
    assert 'href="/crm/contacts/new"' in listing and "New contact" in listing
    assert listing.index('aria-label="CRM navigation"') < listing.index("<h1>Contacts")
    form = client.get("/crm/contacts/new")
    assert form.status_code == 200 and 'action="/crm/contacts"' in form.text
    assert (
        client.post(
            "/crm/contacts", headers=ORIGIN, data={"first_name": ""}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/crm/contacts", headers=ORIGIN, data={"email": "invalid"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/crm/contacts",
            headers=ORIGIN,
            data={"first_name": "Test", "function:unknown": "yes"},
        ).status_code
        == 422
    )
    response = client.post(
        "/crm/contacts",
        headers=ORIGIN,
        data={
            "first_name": "Ada",
            "last_name": "Review",
            "email": "ada@example.test",
            "phone": "+41 44 123 45 67",
            "address_type": "work",
            "mailbox_type": "Personal Mailbox",
            "function:SPOC": "yes",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    detail_url = response.headers["location"]
    with factory() as session:
        contact = session.scalar(
            select(CRMContact).where(CRMContact.label == "Ada Review")
        )
        assert contact.source_row_id is None and contact.function == "SPOC"
        assert contact.profile["email"] == "ada@example.test"
        version = contact.version
    assert "Ada Review" in client.get(detail_url).text
    assert "Ada Review" in client.get("/crm/contacts?q=Ada").text
    assert (
        client.post(
            detail_url,
            headers=ORIGIN,
            data={"version": str(version), "command": "archive"},
        ).status_code
        == 200
    )
    assert "Archived contact" in client.get(detail_url).text
    mailbox = client.post(
        "/crm/contacts",
        headers=ORIGIN,
        data={"email": "alerts@example.test", "mailbox_type": "Shared Mailbox"},
    )
    assert mailbox.status_code == 200
    assert "alerts@example.test" in mailbox.text and "Shared Mailbox" in mailbox.text
