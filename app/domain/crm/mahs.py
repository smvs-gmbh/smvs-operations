"""MAH master records and the initial, insert-only Airtable mapping."""

from sqlalchemy import select

from app.core.db.models import (
    AcquiredArtifact,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.domain.crm.imports import SOURCE
from app.domain.models import CRMMah
from app.integration.artifacts.storage import utcnow

CONTRACT_STATUSES = {
    "unknown": "Unknown",
    "active": "Active contract",
    "no_contract": "No contract",
    "ended": "Contract ended",
}


def seed_staged_mahs(session):
    dataset_id = session.scalar(
        select(StagingDataset.id)
        .join(AcquiredArtifact, AcquiredArtifact.id == StagingDataset.artifact_id)
        .join(ProcessingRun, ProcessingRun.id == StagingDataset.processing_run_id)
        .where(
            AcquiredArtifact.source_name == SOURCE,
            AcquiredArtifact.report_type == "MAH",
            ProcessingRun.status == "staged",
        )
        .order_by(StagingDataset.id.desc())
        .limit(1)
    )
    if dataset_id is None:
        raise ValueError("Stage a MAH export first.")
    existing = set(session.scalars(select(CRMMah.airtable_id)))
    created = 0
    now = utcnow()
    rows = session.scalars(
        select(StagingRow).where(StagingRow.staging_dataset_id == dataset_id)
    )
    for row in rows:
        data = row.raw_row_json
        identity = data["RECORD_ID"].strip()
        if identity in existing:
            continue
        name = data["MAH Name"].strip()
        gln = data.get("GLN", "").strip()
        uid = data.get("UID", "").strip()
        if not name or len(name) > 255 or max(len(identity), len(gln), len(uid)) > 100:
            raise ValueError(
                f"Invalid MAH identity fields in staged record {row.source_row_number}."
            )
        session.add(
            CRMMah(
                airtable_id=identity,
                name=name,
                gln=gln or None,
                uid=uid or None,
                registration_checked=1
                if data.get("Checked", "").strip().casefold() == "checked"
                else None,
                contract_status="unknown",
                source_row_id=row.id,
                created_at=now,
                updated_at=now,
            )
        )
        existing.add(identity)
        created += 1
    return created


def main():
    from app.core.db.session import SessionFactory

    with SessionFactory() as session:
        count = seed_staged_mahs(session)
        session.commit()
    print(f"{count} MAH master records created.")


if __name__ == "__main__":
    main()
