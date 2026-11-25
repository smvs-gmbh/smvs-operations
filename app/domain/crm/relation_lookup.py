"""Whitelisted typed conditions shared by CRM relation lookups."""

from datetime import date
from decimal import Decimal, InvalidOperation

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


def normalise_structured_lookup(
    value, *, field_types, output_keys, selection_fields, default_field
):
    if not isinstance(value, dict):
        raise ValueError("Select valid relation lookup settings.")  # noqa: TRY004 -- uniform validation contract
    if set(value) - {"match", "conditions", "selection", "outputs"}:
        raise ValueError("Select valid relation lookup settings.")
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
            or field not in field_types
            or not isinstance(operator, str)
        ):
            raise ValueError("Select a valid lookup field and operator.")
        kind = field_types[field]
        if operator not in (NUMBER_OPS if kind in ("number", "date") else TEXT_OPS):
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
        elif kind == "date":
            try:
                if not isinstance(raw, str):
                    raise ValueError()  # noqa: TRY004 -- uniform validation contract
                raw = date.fromisoformat(raw).isoformat()
            except ValueError:
                raise ValueError(
                    "Enter a valid ISO lookup date (YYYY-MM-DD)."
                ) from None
        elif not isinstance(raw, str) or not raw.strip() or len(raw) > 200:
            raise ValueError("Enter a valid lookup text value.")
        else:
            raw = raw.strip()
        cleaned.append({"field": field, "operator": operator, "value": raw})
    selection = value.get("selection", {"rule": "unique", "field": default_field})
    if not isinstance(selection, dict) or set(selection) - {"rule", "field"}:
        raise ValueError("Select a valid lookup selection rule.")
    rule, field = selection.get("rule"), selection.get("field", default_field)
    if rule not in ("unique", "min", "max") or field not in selection_fields:
        raise ValueError(
            "Select Unique match, Minimum or Maximum with a numeric or date field."
        )
    outputs = value.get("outputs", [])
    if not isinstance(outputs, list) or any(
        not isinstance(k, str) or k not in output_keys for k in outputs
    ):
        raise ValueError("Select valid lookup output fields.")
    return {
        "match": match,
        "conditions": cleaned,
        "selection": {"rule": rule, "field": field},
        "outputs": list(dict.fromkeys(outputs)),
    }


def matches_condition(values, condition, field_types):
    value, operator = values[condition["field"]], condition["operator"]
    empty = value is None or value == ""
    if operator == "empty":
        return empty
    if operator == "not_empty":
        return not empty
    if empty:
        return False
    if field_types[condition["field"]] == "number":
        left, right = Decimal(str(value)), Decimal(condition["value"])
    elif field_types[condition["field"]] == "date":
        left = value if isinstance(value, date) else date.fromisoformat(value)
        right = date.fromisoformat(condition["value"])
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


def select_candidates(records, config, field_types):
    conditions = config["conditions"]
    combine = all if config["match"] == "and" else any
    candidates = [
        v
        for v in records
        if not conditions
        or combine(matches_condition(v, c, field_types) for c in conditions)
    ]
    rule, field = config["selection"]["rule"], config["selection"]["field"]
    if rule != "unique":
        candidates = [v for v in candidates if v[field] is not None and v[field] != ""]
        if candidates:
            extreme = (min if rule == "min" else max)(v[field] for v in candidates)
            candidates = [v for v in candidates if v[field] == extreme]
    return candidates
