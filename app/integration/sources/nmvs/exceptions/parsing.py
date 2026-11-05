import json
from datetime import UTC, datetime

from app.integration.sources.nmvs.parsing import record_hash


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def parse_page(content, requested_page):
    if len(content) > 30_000_000:
        raise ValueError("Exception page exceeds size limit.")
    payload = json.loads(content)
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("Invalid exception page.")
    rows = payload.get("data")
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError("Invalid exception page data.")
    if (
        payload.get("isTruncated") is not False
        or payload.get("isOverLimit", False) is not False
    ):
        raise ValueError("Incomplete exception result cannot be published.")
    for field in ("page", "pages", "records", "totalRecords", "pageSize"):
        if not integer(payload.get(field)):
            raise ValueError("Missing exception pagination metadata.")
    if (
        payload["page"] != requested_page
        or payload["records"] not in (len(rows), payload["totalRecords"])
        or payload["pageSize"] != 1000
        or payload["pages"] > 1000
        or payload["totalRecords"] > 1_000_000
        or (payload["pages"] == 0 and payload["totalRecords"] != 0)
    ):
        raise ValueError("Inconsistent exception pagination.")
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("Invalid exception observation.")
        alert = row.get("uniqueAlertID")
        if (
            not isinstance(alert, str)
            or not alert.strip()
            or alert != alert.strip()
            or len(alert) > 100
        ):
            raise ValueError(
                "Exception has no usable Alert ID; source retained, publication refused."
            )
        for k, v in row.items():
            if (
                not isinstance(k, str)
                or isinstance(v, (dict, list))
                or isinstance(v, str)
                and len(v) > 10000
            ):
                raise TypeError("Invalid exception field value.")
        for field in ("manualEntry", "isIntermarket"):
            if row.get(field) is not None and not isinstance(row[field], bool):
                raise ValueError("Invalid exception boolean.")
    return payload


def parse_pages(contents):
    if not contents:
        raise ValueError("No exception pages.")
    parsed = [parse_page(data, i) for i, data in enumerate(contents, 1)]
    first = parsed[0]
    pages = max(1, first["pages"])
    if len(parsed) != pages or any(
        (p["pages"], p["totalRecords"], p["pageSize"])
        != (first["pages"], first["totalRecords"], first["pageSize"])
        for p in parsed
    ):
        raise ValueError("Exception query pagination is incomplete or changed.")
    rows = [r for p in parsed for r in p["data"]]
    if len(rows) != first["totalRecords"]:
        raise ValueError("Exception query record count is incomplete.")
    seen = {}
    for row in rows:
        identifier = row["uniqueAlertID"]
        if identifier in seen:
            # Fail rather than silently lose a different observation at a page boundary.
            raise ValueError(
                "Duplicate Alert ID within one query; completeness needs review."
            )
        seen[identifier] = record_hash(row)
    return rows


def source_time(value):
    if not value:
        return None, "missing"
    if not isinstance(value, str):
        return None, "invalid"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None, "missing_offset"
        return parsed.astimezone(UTC).replace(tzinfo=None), "parsed"
    except ValueError:
        return None, "invalid"
