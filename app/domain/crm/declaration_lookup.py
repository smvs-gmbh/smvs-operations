"""Read-only, deterministic MAH-to-declaration lookup for the local CRM trial."""

from collections import defaultdict

from sqlalchemy import select

from app.core.db.models import StagingRow
from app.domain.models import CRMSelfDeclaration

LOOKUP_KEYS = (
    "sd_year",
    "sd_packs",
    "sd_sales_group",
    "sd_status",
    "sd_declaration",
    "sd_selection",
)


def normalise_lookup(value=None):
    if value is None:
        return {"rule": "latest", "year": None}
    if not isinstance(value, dict) or set(value) - {"rule", "year"}:
        raise ValueError("Select a valid self-declaration discriminator.")
    rule, year = value.get("rule"), value.get("year")
    if rule not in ("latest", "year") or (
        rule == "year" and (type(year) is not int or not 1900 <= year <= 9999)
    ):
        raise ValueError("Select highest data year or a specific data year.")
    if rule == "latest" and year is not None:
        raise ValueError("Highest data year does not take a fixed year.")
    return {"rule": rule, "year": year}


def declaration_values(session, mah_ids, selection=None):
    selection = normalise_lookup(selection)
    grouped = defaultdict(list)
    if mah_ids:
        statement = (
            select(CRMSelfDeclaration, StagingRow.raw_row_json)
            .outerjoin(StagingRow, CRMSelfDeclaration.source_row_id == StagingRow.id)
            .where(CRMSelfDeclaration.mah_id.in_(mah_ids))
        )
        if selection["rule"] == "year":
            statement = statement.where(
                CRMSelfDeclaration.declaration_year == selection["year"]
            )
        for record, raw in session.execute(statement):
            grouped[record.mah_id].append((record, raw or {}))
    result = {}
    for mah_id in mah_ids:
        candidates = grouped[mah_id]
        if candidates and selection["rule"] == "latest":
            year = max(record.declaration_year for record, _ in candidates)
            candidates = [
                (record, raw)
                for record, raw in candidates
                if record.declaration_year == year
            ]
        values = dict.fromkeys(LOOKUP_KEYS)
        values["sd_selection"] = (
            "No declaration" if not candidates else "Data error: duplicate MAH/year"
        )
        if len(candidates) == 1:
            record, raw = candidates[0]
            values.update(
                sd_year=record.declaration_year,
                sd_packs=record.packs_sold,
                sd_sales_group=raw.get("RX sales group"),
                sd_status=record.status,
                sd_declaration=record.record_label,
                sd_selection="Matched",
                _sd_source_id=record.id,
            )
        result[mah_id] = values
    return result
