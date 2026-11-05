import re
from collections import OrderedDict

from app.integration.sources.nmvs.exceptions.parsing import source_time
from app.integration.sources.nmvs.pack_audit.parsing import details


def summarize(events, *, alert_id=None, transaction_id=None):
    rows = []
    for index, raw in enumerate(events, 1):
        at, quality = source_time(raw.get("Date and Time (UTC)"))
        fields = details(raw.get("Event Details"))
        rows.append(
            {
                "raw": raw,
                "row": index,
                "at": at,
                "time_quality": quality,
                "fields": fields,
            }
        )
    rows.sort(key=lambda e: (e["at"] is None, e["at"] or 0, e["row"]))
    grouped = OrderedDict()
    for row in rows:
        tx = row["raw"].get("Transaction ID")
        grouped.setdefault(("tx", tx) if tx else ("row", row["row"]), []).append(row)
    groups = []
    for index, (identity, items) in enumerate(grouped.items(), 1):

        def unique(field, items=items):
            values = {e["fields"][field] for e in items if e["fields"].get(field)}
            return next(iter(values)) if len(values) == 1 else None

        event_codes = {
            e["raw"]["Event Code"] for e in items if e["raw"].get("Event Code")
        }
        reported_codes = event_codes | {
            e["fields"][k]
            for e in items
            for k in ("AlertCode", "InternalErrorCode")
            if e["fields"].get(k)
        }
        codes = sorted(
            code for code in reported_codes if re.fullmatch(r"A[0-9]+", code)
        )
        error = bool(codes) or any(
            e["raw"].get("Severity") in ("ERROR", "CRITICAL") for e in items
        )
        verified = any(
            e["raw"].get("Event Name")
            in ("PackVerificationSuccessful", "IntermarketSuccessfulPackVerification")
            for e in items
        )
        created = any(e["raw"].get("Event Name") == "PpdNewPackCreated" for e in items)
        before, actual = unique("InitialState"), unique("ActualState")
        changed = bool(before and actual and before != actual and not error)
        matched = bool(
            (transaction_id and identity == ("tx", transaction_id))
            or (
                alert_id
                and any(
                    alert_id == e["fields"].get(k)
                    for e in items
                    for k in (
                        "AlertId",
                        "AlertID",
                        "UniqueAlertId",
                        "UniqueAlertID",
                        "UniquePackReturnCode",
                    )
                )
            )
        )
        title = (
            "Pack created"
            if created
            else "State change reported by source"
            if changed
            else "Attempt with an error"
            if error
            else "Verification reported as successful"
            if verified
            else "Other transaction"
        )
        operation = unique("AttemptedOperation")
        operation_labels = {
            "CREATED": "Create",
            "EXPORTED": "Export",
            "VERIFIED": "Verify",
            "SUPPLIED": "Supply",
            "DESTROYED": "Destroy",
            "ACTIVE": "Reactivate",
        }
        receivers = sorted(
            {
                e["fields"]["AlertEventSource"]
                for e in items
                if e["raw"].get("Event Name") == "Alert"
                and e["fields"].get("AlertEventSource")
            }
        )
        group = {
            "id": index,
            "items": items,
            "at": items[0]["at"],
            "transaction_id": identity[1] if identity[0] == "tx" else None,
            "title": title,
            "kind": "error"
            if error
            else "change"
            if changed
            else "created"
            if created
            else "other",
            "before": before,
            "actual": actual,
            "target": unique("TargetState"),
            "operation": operation_labels.get(operation, operation),
            "market": unique("Market"),
            "location": unique("Location"),
            "codes": codes,
            "matched": matched,
            "receivers": receivers,
            "description": next(
                (
                    e["raw"].get("Event Message")
                    for e in sorted(
                        items, key=lambda r: not bool(r["fields"].get("ActualState"))
                    )
                    if e["raw"].get("Event Message")
                ),
                None,
            ),
            "reported_change_time": unique("TimestampOfChange"),
        }
        groups.append(group)
    targets = [g for g in groups if g["matched"]]
    selected = targets[0] if len(targets) == 1 else None
    last_change = None
    if selected and selected["at"]:
        changes = [
            g
            for g in groups
            if g["kind"] == "change" and g["at"] and g["at"] < selected["at"]
        ]
        last_change = changes[-1] if changes else None
    relevant = [g for g in groups if g["kind"] != "other" or g["matched"]]
    milestones = (
        relevant
        if len(relevant) <= 6
        else relevant[:2]
        + (
            [selected]
            if selected and selected not in relevant[:2] + relevant[-2:]
            else []
        )
        + relevant[-2:]
    )
    return {
        "groups": groups,
        "relevant": relevant,
        "milestones": milestones,
        "selected": selected,
        "last_change": last_change,
        "event_count": len(events),
        "transaction_count": len(groups),
        "match_count": len(targets),
        "unknown_times": sum(e["at"] is None for e in rows),
        "omitted_milestones": max(0, len(relevant) - len(milestones)),
    }
