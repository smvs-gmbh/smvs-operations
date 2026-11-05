"""Import contact profiles from a staged Airtable export."""

import argparse
from pathlib import Path

from sqlalchemy import select

from app.core.db.models import (
    AcquiredArtifact,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.domain.crm.imports import SOURCE, parse_export, stage_export
from app.domain.models import CRMContact

CONTACT_PROFILE_COLUMNS = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "email": "Email",
    "phone": "Phone",
    "mailbox_type": "Mailbox Type",
}
MAILBOX_TYPES = ("Personal Mailbox", "Shared Mailbox")


def seed_staged_contacts(session):
    dataset_id = session.scalar(
        select(StagingDataset.id)
        .join(AcquiredArtifact, AcquiredArtifact.id == StagingDataset.artifact_id)
        .join(ProcessingRun, ProcessingRun.id == StagingDataset.processing_run_id)
        .where(
            AcquiredArtifact.source_name == SOURCE,
            AcquiredArtifact.report_type == "Contacts",
            ProcessingRun.status == "staged",
        )
        .order_by(StagingDataset.id.desc())
        .limit(1)
    )
    if dataset_id is None:
        raise ValueError("Stage a Contacts export first.")
    existing = {
        contact.airtable_id: contact
        for contact in session.scalars(select(CRMContact).with_for_update())
    }
    changed = 0
    for row in session.scalars(
        select(StagingRow).where(StagingRow.staging_dataset_id == dataset_id)
    ):
        data = row.raw_row_json
        identity = data["RECORD_ID2"].strip()
        defaults = {
            field: data[header].strip()
            for field, header in CONTACT_PROFILE_COLUMNS.items()
            if data.get(header, "").strip()
        }
        contact = existing.get(identity)
        if contact is not None:
            profile = defaults | (contact.profile or {})
            if profile != (contact.profile or {}) or contact.source_row_id != row.id:
                contact.profile = profile or None
                contact.source_row_id = row.id
                changed += 1
            continue
        session.add(
            CRMContact(
                airtable_id=identity,
                label=data["Record Id"].strip(),
                function=data.get("Function", "").strip() or None,
                source_row_id=row.id,
                profile=defaults or None,
            )
        )
        changed += 1
    return changed


def main():
    from app.core.db.session import SessionFactory

    parser = argparse.ArgumentParser(description="Import an Airtable Contacts export.")
    parser.add_argument("export", nargs="?", type=Path)
    args = parser.parse_args()
    with SessionFactory() as session:
        if args.export:
            content = args.export.read_bytes()
            stage_export(
                session, parse_export("Contacts", content), content, args.export.name
            )
        count = seed_staged_contacts(session)
        session.commit()
    print(f"{count} contacts created or updated.")


if __name__ == "__main__":
    main()
