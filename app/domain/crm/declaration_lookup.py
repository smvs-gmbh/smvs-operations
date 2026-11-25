"""Read-only, deterministic MAH-to-declaration lookup for the local CRM trial."""

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

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


# Stable keys are persisted; labels can change without breaking a view.
FILTER_FIELDS = {
    "sd_year": "number",
    "sd_packs": "number",
    "sd_sales_group": "text",
    "sd_status": "text",
}
NUMBER_OPS = {
    "equals",
    "not_equals",
    "greater_than",
    "greater_equal",
    "less_than",
    "less_equal",
    "empty",
    "not_empty",
}
TEXT_OPS = {"equals", "not_equals", "contains", "empty", "not_empty"}


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
    if set(value) - {"match", "conditions", "selection", "outputs"}:
        raise ValueError("Select valid self-declaration lookup settings.")
    match = value.get("match", "and")
    conditions = value.get("conditions", [])
    if (
        match not in ("and", "or")
        or not isinstance(conditions, list)
        or len(conditions) > 8
    ):
        raise ValueError("Use up to eight lookup conditions with AND or OR.")
    cleaned = []
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) - {
            "field",
            "operator",
            "value",
        }:
            raise ValueError("Select valid lookup conditions.")
        field, operator = condition.get("field"), condition.get("operator")
        if (
            not isinstance(field, str)
            or field not in FILTER_FIELDS
            or not isinstance(operator, str)
        ):
            raise ValueError("Select a valid lookup field and operator.")
        kind = FILTER_FIELDS[field]
        if operator not in (NUMBER_OPS if kind == "number" else TEXT_OPS):
            raise ValueError("Select an operator supported by the lookup field.")
        raw = condition.get("value", "")
        if operator in ("empty", "not_empty"):
            raw = ""
        elif kind == "number":
            try:
                number = Decimal(str(raw))
                if type(raw) is bool or not number.is_finite() or len(str(raw)) > 80:
                    raise ValueError()
                raw = str(number)
            except (ValueError, InvalidOperation):
                raise ValueError("Enter a valid numeric lookup value.") from None
        elif not isinstance(raw, str) or not raw.strip() or len(raw) > 200:
            raise ValueError("Enter a valid lookup text value.")
        else:
            raw = raw.strip()
        cleaned.append({"field": field, "operator": operator, "value": raw})
    selection = value.get("selection", {"rule": "unique", "field": "sd_year"})
    if not isinstance(selection, dict) or set(selection) - {"rule", "field"}:
        raise ValueError("Select a valid lookup selection rule.")
    rule, field = selection.get("rule"), selection.get("field", "sd_year")
    if rule not in ("unique", "min", "max") or field not in ("sd_year", "sd_packs"):
        raise ValueError(
            "Select Unique match, Minimum or Maximum with a numeric field."
        )
    outputs = value.get("outputs", ["sd_year", "sd_selection"])
    if not isinstance(outputs, list) or any(
        not isinstance(k, str) or k not in LOOKUP_KEYS for k in outputs
    ):
        raise ValueError("Select valid lookup output fields.")
    return {
        "match": match,
        "conditions": cleaned,
        "selection": {"rule": rule, "field": field},
        "outputs": list(dict.fromkeys(["sd_year", "sd_selection", *outputs])),
    }


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


def matches_condition(values, condition):
    value, operator = values[condition["field"]], condition["operator"]
    empty = value is None or value == ""
    if operator == "empty":
        return empty
    if operator == "not_empty":
        return not empty
    if empty:
        return False
    if FILTER_FIELDS[condition["field"]] == "number":
        left, right = Decimal(str(value)), Decimal(condition["value"])
    else:
        left, right = str(value).casefold(), condition["value"].casefold()
    if operator == "equals":
        return left == right
    if operator == "not_equals":
        return left != right
    if operator == "contains":
        return right in left
    return {
        "greater_than": lambda: left > right,
        "greater_equal": lambda: left >= right,
        "less_than": lambda: left < right,
        "less_equal": lambda: left <= right,
    }[operator]()


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
        conditions = selection["conditions"]
        combine = all if selection["match"] == "and" else any
        candidates = [
            v
            for v in all_candidates
            if not conditions or combine(matches_condition(v, c) for c in conditions)
        ]
        rule, basis = selection["selection"]["rule"], selection["selection"]["field"]
        if candidates and rule != "unique":
            usable = [v for v in candidates if v[basis] is not None]
            if usable:
                extreme = (min if rule == "min" else max)(v[basis] for v in usable)
                candidates = [v for v in usable if v[basis] == extreme]
            else:
                candidates = []
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
