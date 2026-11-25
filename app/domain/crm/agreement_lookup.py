"""Select one explicitly linked agreement for each MAH without arbitrary tie-breaking."""

from collections import defaultdict

from sqlalchemy import select

from app.core.db.models import StagingRow
from app.domain.crm.relation_lookup import (
    normalise_structured_lookup,
    select_candidates,
)
from app.domain.models import CRMAgreement, CRMAgreementMAH

FIELDS = {
    "ag_contract_id": "text",
    "ag_contractor": "text",
    "ag_status": "text",
    "ag_signing_date": "date",
    "ag_start_date": "text",
    "ag_termination_date": "text",
}
OUTPUT_KEYS = (*FIELDS, "ag_selection")


def normalise_agreement_lookup(value=None):
    if value is None:
        value = {}
    return normalise_structured_lookup(
        value,
        field_types=FIELDS,
        output_keys=OUTPUT_KEYS,
        selection_fields=("ag_signing_date",),
        default_field="ag_signing_date",
    )


def agreement_values(session, mah_ids, selection=None, *, linked_records=None):
    config = normalise_agreement_lookup(selection)
    grouped = defaultdict(list)
    if linked_records is None:
        linked_records = (
            session.execute(
                select(CRMAgreementMAH.mah_id, CRMAgreement)
                .join(CRMAgreement)
                .where(CRMAgreementMAH.mah_id.in_(mah_ids))
            ).all()
            if mah_ids
            else []
        )
    source_ids = {
        record.source_row_id for _, record in linked_records if record.source_row_id
    }
    sources = (
        dict(
            session.execute(
                select(StagingRow.id, StagingRow.raw_row_json).where(
                    StagingRow.id.in_(source_ids)
                )
            ).all()
        )
        if source_ids
        else {}
    )
    for mah_id, record in linked_records:
        raw = sources.get(record.source_row_id) or {}
        grouped[mah_id].append(
            {
                "ag_contract_id": record.contract_id,
                "ag_contractor": record.contractor,
                "ag_status": record.status,
                "ag_signing_date": record.signing_date,
                # Source-only date strings retain their original representation, without guessing formats.
                "ag_start_date": raw.get("Start Date"),
                "ag_termination_date": raw.get("Termination Date"),
                "ag_selection": "Matched",
                "_ag_source_id": record.id,
            }
        )
    result = {}
    for mah_id in mah_ids:
        candidates = select_candidates(grouped[mah_id], config, FIELDS)
        values = dict.fromkeys(OUTPUT_KEYS)
        values["ag_selection"] = (
            "No agreement" if not candidates else "Ambiguous selection"
        )
        if len(candidates) == 1:
            values.update(candidates[0])
        result[mah_id] = values
    return result
