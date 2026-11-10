"""Imported MAH role references become durable, repeatable CRM assignments."""

import csv
import io
from datetime import timedelta

from sqlalchemy import select

from app.domain.crm.contacts import seed_staged_contacts
from app.domain.crm.imports import parse_export, stage_export
from app.domain.crm.mah_contacts import plan_mah_contacts, seed_mah_contacts
from app.domain.crm.mahs import seed_staged_mahs
from app.domain.models import CRMContact, CRMMah
from app.integration.artifacts.storage import utcnow


def stage(session, table, rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    content = output.getvalue().encode()
    stage_export(session, parse_export(table, content), content, table + ".csv")


def test_mah_contacts_seed_from_ids_and_labels_preserving_distinct_same_email_contacts(
    portal,
):
    _, factory = portal
    with factory.begin() as session:
        contacts = [
            CRMContact(
                airtable_id="recA",
                label="Primary (shared@example.test)",
                profile={"email": "shared@example.test"},
            ),
            CRMContact(
                airtable_id="recB",
                label="Distribution (shared@example.test)",
                profile={"email": "shared@example.test"},
            ),
        ]
        session.add_all(contacts)
        session.flush()
        stage(
            session,
            "MAH",
            [
                {
                    "RECORD_ID": "mahA",
                    "MAH Name": "Company A",
                    "SPOC": "recA",
                    "Alert contacts": ",".join(contact.label for contact in contacts),
                }
            ],
        )
        assert seed_staged_mahs(session) == 1
        mah = session.scalar(select(CRMMah))
        assert mah.profile["spoc_ids"] == [contacts[0].id]
        assert mah.profile["alert_contact_ids"] == [c.id for c in contacts]
        assert not seed_mah_contacts(session)
        # Explicit choices, including deliberately empty and legacy values, win.
        mah.profile = {"spoc_id": None, "alert_contact_ids": [], "note": "Preserve me"}
        assert not seed_mah_contacts(session)
        assert mah.profile == {
            "spoc_id": None,
            "alert_contact_ids": [],
            "note": "Preserve me",
        }


def test_contact_import_later_repairs_existing_mahs_and_skips_archived_and_ambiguous(
    portal,
):
    _, factory = portal
    with factory.begin() as session:
        stage(
            session,
            "MAH",
            [
                {
                    "RECORD_ID": "mahA",
                    "MAH Name": "Company A",
                    "SPOC": "Primary",
                    "Alert contacts": "recB",
                },
                {
                    "RECORD_ID": "mahB",
                    "MAH Name": "Company B",
                    "SPOC": "Primary,Duplicate",
                    "Alert contacts": "Archived",
                },
                {
                    "RECORD_ID": "mahC",
                    "MAH Name": "Company C",
                    "SPOC": "Primary",
                    "Alert contacts": "recB",
                },
            ],
        )
        seed_staged_mahs(session)
        mahs = session.scalars(select(CRMMah).order_by(CRMMah.name)).all()
        mahs[2].archived_at = utcnow() - timedelta(days=1)
        session.add_all(
            [
                CRMContact(airtable_id="dupA", label="Duplicate"),
                CRMContact(airtable_id="dupB", label="Duplicate"),
                CRMContact(airtable_id="old", label="Archived", archived_at=utcnow()),
                CRMContact(
                    airtable_id="pending",
                    label="Pending",
                    profile={"registration_pending": True},
                ),
            ]
        )
        stage(
            session,
            "Contacts",
            [
                {
                    "RECORD_ID2": "recA",
                    "Record Id": "Primary",
                    "First Name": "First",
                    "Last Name": "Person",
                    "Email": "primary@example.test",
                },
                {
                    "RECORD_ID2": "recB",
                    "Record Id": "Distribution",
                    "First Name": "Second",
                    "Last Name": "Person",
                    "Email": "alerts@example.test",
                },
            ],
        )
        assert seed_staged_contacts(session) == 2
        assert (
            len(mahs[0].profile["spoc_ids"])
            == len(mahs[0].profile["alert_contact_ids"])
            == 1
        )
        assert not mahs[
            1
        ].profile  # Entire ambiguous role stays open; no partial assignment.
        assert not mahs[2].profile  # Archived MAH remains untouched.
        pending = next(
            p for mah, _, p in plan_mah_contacts(session) if mah.id == mahs[1].id
        )
        assert any("Ambiguous match" in item for item in pending)
        assert any("No matching contact" in item for item in pending)
        assert not seed_staged_contacts(session)
        assert not seed_mah_contacts(session)


def test_imported_contact_erasure_preserves_mah_and_blocks_repeat_import(portal):
    from types import SimpleNamespace

    from app.domain.crm.deletion import erase_record
    from app.domain.models import CRMDeletionEvent, CRMEndUser

    _, factory = portal
    with factory.begin() as session:
        stage(
            session,
            "Contacts",
            [
                {
                    "RECORD_ID2": "recWrong",
                    "Record Id": "Wrong contact",
                    "First Name": "Wrong",
                    "Last Name": "Contact",
                    "Email": "",
                },
                {
                    "RECORD_ID2": "recKeep",
                    "Record Id": "Correct contact",
                    "First Name": "Correct",
                    "Last Name": "Contact",
                    "Email": "spoc@example.test",
                },
            ],
        )
        seed_staged_contacts(session)
        wrong = session.scalar(
            select(CRMContact).where(CRMContact.airtable_id == "recWrong")
        )
        kept = session.scalar(
            select(CRMContact).where(CRMContact.airtable_id == "recKeep")
        )
        stage(
            session,
            "MAH",
            [
                {
                    "RECORD_ID": "mahA",
                    "MAH Name": "Moderna example",
                    "SPOC": "recKeep",
                    "Alert contacts": "recWrong,recKeep",
                }
            ],
        )
        seed_staged_mahs(session)
        mah = session.scalar(select(CRMMah))
        user = CRMEndUser(
            name="Keep End User",
            profile={"spoc_id": wrong.id, "alert_contact_ids": [wrong.id, kept.id]},
        )
        session.add(user)
        session.flush()
        mah_id, user_id, wrong_id, kept_id = mah.id, user.id, wrong.id, kept.id
        erase_record(session, wrong, SimpleNamespace(id=1))
    with factory.begin() as session:
        assert session.get(CRMContact, wrong_id) is None
        assert session.get(CRMMah, mah_id).profile["spoc_ids"] == [kept_id]
        assert session.get(CRMMah, mah_id).profile["alert_contact_ids"] == [kept_id]
        assert session.get(CRMEndUser, user_id).profile == {
            "spoc_ids": [],
            "alert_contact_ids": [kept_id],
        }
        audit = session.scalar(select(CRMDeletionEvent))
        assert (
            audit.record_type == "crm_contacts"
            and len(audit.source_identity_hash) == 64
        )
        assert "recWrong" not in audit.source_identity_hash
        assert seed_staged_contacts(session) == 0
        assert session.get(CRMContact, wrong_id) is None
        # Suppression also works for a new export containing the same Airtable identity.
        stage(
            session,
            "Contacts",
            [
                {
                    "RECORD_ID2": "recWrong",
                    "Record Id": "Renamed wrong contact",
                    "First Name": "Renamed",
                    "Last Name": "Contact",
                    "Email": "changed@example.test",
                }
            ],
        )
        assert seed_staged_contacts(session) == 0
        assert (
            session.scalar(
                select(CRMContact).where(CRMContact.airtable_id == "recWrong")
            )
            is None
        )
        assert session.get(CRMMah, mah_id) is not None
