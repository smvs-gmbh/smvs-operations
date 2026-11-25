"""Read-only, deterministic MAH-to-declaration lookup for the local CRM trial."""

from collections import Counter, defaultdict

from sqlalchemy import select

from app.core.db.models import StagingRow
from app.domain.crm.relation_lookup import (
    normalise_structured_lookup,
    select_candidates,
)
from app.domain.models import CRMSelfDeclaration

LOOKUP_KEYS = (
    "sd_year",
    "sd_packs",
    "sd_sales_group",
    "sd_status",
    "sd_declaration",
    "sd_selection",
)


# Stable keys are persisted; labels can change without breaking a view.
FILTER_FIELDS = {
    "sd_year": "number",
    "sd_packs": "number",
    "sd_sales_group": "text",
    "sd_status": "text",
}


def normalise_lookup(value=None):
    if value is None:
        return {"rule": "latest", "year": None}
    if not isinstance(value, dict):
        raise ValueError("Select valid self-declaration lookup settings.")  # noqa: TRY004 -- uniform validation contract
    # Keep the original trial views readable without changing their saved meaning.
    if "rule" in value:
        if set(value) - {"rule", "year"}:
            raise ValueError("Select a valid self-declaration discriminator.")
        rule, year = value.get("rule"), value.get("year")
        if rule not in ("latest", "year") or (
            rule == "year" and (type(year) is not int or not 1900 <= year <= 9999)
        ):
            raise ValueError("Select highest data year or a specific data year.")
        if rule == "latest" and year is not None:
            raise ValueError("Highest data year does not take a fixed year.")
        return {"rule": rule, "year": year}
    return normalise_structured_lookup(
        value,
        field_types=FILTER_FIELDS,
        output_keys=LOOKUP_KEYS,
        selection_fields=("sd_year", "sd_packs"),
        default_field="sd_year",
    )


def structured_lookup(value=None):
    value = normalise_lookup(value)
    if "rule" not in value:
        return value
    return {
        "match": "and",
        "conditions": (
            [{"field": "sd_year", "operator": "equals", "value": str(value["year"])}]
            if value["rule"] == "year"
            else []
        ),
        "selection": {
            "rule": "unique" if value["rule"] == "year" else "max",
            "field": "sd_year",
        },
        "outputs": list(LOOKUP_KEYS),
    }


def source_values(record, raw):
    return {
        "sd_year": record.declaration_year,
        "sd_packs": record.packs_sold,
        "sd_sales_group": raw.get("RX sales group"),
        "sd_status": record.status,
        "sd_declaration": record.record_label,
        "sd_selection": "Matched",
        "_sd_source_id": record.id,
    }


def declaration_values(session, mah_ids, selection=None):
    selection = structured_lookup(selection)
    grouped = defaultdict(list)
    if mah_ids:
        statement = (
            select(CRMSelfDeclaration, StagingRow.raw_row_json)
            .outerjoin(StagingRow, CRMSelfDeclaration.source_row_id == StagingRow.id)
            .where(CRMSelfDeclaration.mah_id.in_(mah_ids))
        )
        for record, raw in session.execute(statement):
            grouped[record.mah_id].append((record, raw or {}))
    result = {}
    for mah_id in mah_ids:
        all_candidates = [source_values(record, raw) for record, raw in grouped[mah_id]]
        candidates = select_candidates(all_candidates, selection, FILTER_FIELDS)
        counts = Counter(v["sd_year"] for v in all_candidates)
        # Filters must never hide a duplicate source for the selected year.
        duplicate = any(counts[v["sd_year"]] > 1 for v in candidates)
        values = dict.fromkeys(LOOKUP_KEYS)
        values["sd_selection"] = (
            "Data error: duplicate MAH/year"
            if duplicate
            else "No declaration"
            if not candidates
            else "Ambiguous selection"
        )
        if len(candidates) == 1 and not duplicate:
            values.update(candidates[0])
        result[mah_id] = values
    return result
