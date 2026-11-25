"""Import declarations without creating duplicate MAH/year business records."""

import hashlib
import json
from collections import defaultdict

from sqlalchemy import select

from app.core.db.models import StagingDataset, StagingRow
from app.domain.crm.imports import linked_values
from app.domain.crm.mahs import legacy_test_mah
from app.domain.models import CRMMah, CRMSelfDeclaration

TABLE = "Self-declarations"


def identity(value):
    return value.strip().casefold()


def seed_self_declarations(session, dataset_id):
    session.scalar(
        select(StagingDataset.id)
        .where(StagingDataset.id == dataset_id)
        .with_for_update()
    )
    rows = session.scalars(
        select(StagingRow)
        .where(StagingRow.staging_dataset_id == dataset_id)
        .order_by(StagingRow.source_row_number)
    ).all()
    names, references = defaultdict(set), defaultdict(set)
    for mah, source in session.execute(
        select(CRMMah, StagingRow.raw_row_json)
        .outerjoin(StagingRow, CRMMah.source_row_id == StagingRow.id)
        .order_by(CRMMah.id)
        .with_for_update()
    ):
        names[identity(mah.name)].add(mah.id)
        for label in linked_values((source or {}).get("Selfdeclarations", "")):
            references[identity(label)].add(mah.id)

    # Lock MAHs before reading existing business keys so concurrent imports
    # through this service cannot create the same assigned MAH/year pair.
    existing = set(
        session.scalars(select(CRMSelfDeclaration.source_key).with_for_update())
    )
    pairs = set(
        session.execute(
            select(CRMSelfDeclaration.mah_id, CRMSelfDeclaration.declaration_year)
            .where(CRMSelfDeclaration.mah_id.is_not(None))
            .with_for_update()
        ).all()
    )
    planned = []
    created = 0
    for row in rows:
        raw = row.raw_row_json
        # The export has display labels, including duplicates, but no Airtable record key.
        key = hashlib.sha256(
            json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        if key in existing:
            continue
        label = raw["Record Id"].strip()
        name = raw["MAH Name"].strip()
        if legacy_test_mah(name):
            continue
        named = names[identity(name)]
        linked = references[identity(label)]
        candidates = linked & named if linked and named else linked or named
        year = int(raw["Declaration year"])
        packs = int(raw["RX packs sold"]) if raw["RX packs sold"].strip() else None
        if not name or not 1900 <= year <= 9999 or (packs is not None and packs < 0):
            raise ValueError(
                f"Invalid self-declaration at source row {row.source_row_number}."
            )
        mah_id = next(iter(candidates)) if len(candidates) == 1 else None
        if mah_id is not None:
            pair = (mah_id, year)
            if pair in pairs:
                raise ValueError(
                    "Duplicate self-declaration for MAH/data year. Review the retained source rows before importing."
                )
            pairs.add(pair)
        planned.append(
            CRMSelfDeclaration(
                source_key=key,
                source_row_id=row.id,
                record_label=label,
                source_mah_name=name,
                mah_id=mah_id,
                declaration_year=year,
                packs_sold=packs,
                status=raw.get("Status", "").strip() or None,
            )
        )
        existing.add(key)
        created += 1
    session.add_all(planned)
    return created
