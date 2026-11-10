"""Map the published w7AWGA form by stable Tally field keys, not translated labels."""

import re
from datetime import UTC, datetime

FIELDS = {
    "name": "GRdqzQ",
    "gln": "O75bzk",
    "uid": "Vz5b0N",
    "organisation_type": "D7d96q",
    "street": "l6dXkB",
    "postal_code": "RD51yd",
    "city": "o2MYLe",
    "country": "GRdaAp",
    "first_name": "Pz5b6P",
    "last_name": "ExQZXA",
    "function": "roAJ6p",
    "email": "O75KM7",
    "phone": "Vz5XOJ",
    "supplier": "Pz5LJ5",
    "software": "ExQe7X",
    "licence": "WzMdJN",
    "security_question": "4KxRVk",
    "security_answer": "z7qrj0",
    "notes": "jlQXAx",
    "terms_accepted": "0exPXN",
}
REQUIRED = {
    "name",
    "gln",
    "organisation_type",
    "street",
    "postal_code",
    "city",
    "country",
    "first_name",
    "last_name",
    "function",
    "email",
    "phone",
    "security_question",
    "security_answer",
}
SECRET_FIELDS = {"security_question", "security_answer"}


def submission_shape(payload):
    """Safe rejection diagnostics: fixed field names/types only, never answers."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        return {"structure": "invalid"}
    data = payload["data"]
    fields = data.get("fields")
    if not isinstance(fields, list):
        return {"fields": "not_a_list"}
    source = {
        f.get("key"): f
        for f in fields[:100]
        if isinstance(f, dict) and isinstance(f.get("key"), str)
    }
    result = {}
    for name, key in FIELDS.items():
        field = source.get("question_" + key)
        if field is None:
            result[name] = "missing"
            continue
        value = field.get("value")
        kind = type(value).__name__
        if isinstance(value, list):
            options = field.get("options", [])
            ids = (
                {
                    o["id"]
                    for o in options
                    if isinstance(o, dict) and isinstance(o.get("id"), str)
                }
                if isinstance(options, list)
                else set()
            )
            kind += f":count={len(value)}:options={len(ids)}"
        elif isinstance(value, str) and not value.strip():
            kind += ":empty"
        result[name] = kind
    return {
        "form_matches": data.get("formId") == "w7AWGA",
        "event_matches": payload.get("eventType") == "FORM_RESPONSE",
        "field_count": len(fields),
        "gln_format_valid": bool(
            re.fullmatch(
                r"\d{13}", source.get("question_" + FIELDS["gln"], {}).get("value", "")
            )
        )
        if isinstance(source.get("question_" + FIELDS["gln"], {}).get("value"), str)
        else False,
        "known_fields": result,
    }


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("A UTC submission timestamp is required.")
    return result.astimezone(UTC).replace(tzinfo=None)


def parse_submission(payload):
    if payload.get("eventType") != "FORM_RESPONSE":
        raise ValueError("Unsupported event type.")
    data = payload["data"]
    if data.get("formId") != "w7AWGA":
        raise ValueError("Unexpected registration form.")
    event, submission = payload["eventId"], data["submissionId"]
    if any(
        not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", v)
        for v in (event, submission)
    ):
        raise ValueError("Invalid event identity.")
    source = {}
    fields = data["fields"]
    if not isinstance(fields, list) or len(fields) > 100:
        raise ValueError("Invalid registration fields.")
    for field in fields:
        key = field["key"]
        if key in source:
            raise ValueError("Duplicate field key.")
        source[key] = field
    values = {}
    for name, key in FIELDS.items():
        field = source.get("question_" + key, {})
        value = field.get("value", "")
        if name == "terms_accepted":
            if isinstance(value, list):
                options = {o["id"] for o in field.get("options", [])}
                value = len(value) == 1 and value[0] in options
            values[name] = value is True
            continue
        if isinstance(value, list):
            options = {o["id"]: o["text"] for o in field.get("options", [])}
            if len(value) != 1 or value[0] not in options:
                raise ValueError("Choose one valid option.")
            value = options[value[0]]
        if value is None:
            value = ""
        if not isinstance(value, str) or len(value) > (
            2000 if name in ("notes", "licence") else 500
        ):
            raise ValueError("Registration field exceeds its limit.")
        # Preserve the security answer exactly; it is needed for manual NMVS entry.
        values[name] = value if name in SECRET_FIELDS else value.strip()
    validate_values(values)
    created = timestamp(data["createdAt"])
    return event, submission, created, values


def validate_values(values):
    if not isinstance(values, dict) or set(values) != set(FIELDS):
        raise ValueError("Invalid registration fields.")
    if values["terms_accepted"] is not True or any(
        not isinstance(v, str) or len(v) > (2000 if k in ("notes", "licence") else 500)
        for k, v in values.items()
        if k != "terms_accepted"
    ):
        raise ValueError("Invalid registration field types or sizes.")
    if len(values["name"]) > 255:
        raise ValueError("The organisation name is too long.")
    if any(not values[k].strip() for k in REQUIRED) or not values["terms_accepted"]:
        raise ValueError("Required registration information is missing.")
    if (
        not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", values["email"])
        or len(values["email"]) > 254
    ):
        raise ValueError("Invalid email address.")
    if not re.fullmatch(r"\d{13}", values["gln"]):
        raise ValueError("A 13-digit GLN is required.")
