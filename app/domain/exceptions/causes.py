"""Versioned local investigation guidance; not an AMS-Hub code catalogue."""

CATEGORIES = {
    "unknown": {
        "label": "Not yet established",
        "hint": "Start with the original exception and pack history. Record what is still missing.",
        "checks": [
            ("context", "Review the original request, error and pack state"),
            ("history", "Compare the pack audit trail and relevant upload history"),
        ],
    },
    "data_capture": {
        "label": "Scanning or manual-entry error",
        "hint": "Check whether the values sent to NMVS match the physical pack. A batch or serial mismatch alone does not prove a scanning error.",
        "checks": [
            (
                "pack",
                "Compare product, batch, serial and expiry with the physical pack",
            ),
            ("input", "Check scanner configuration, raw scan or manual-entry values"),
        ],
    },
    "repeat_operation": {
        "label": "Repeated operation on the same pack",
        "hint": "For example, Destroy followed by Destroy. Establish the earlier successful operation and the later attempt.",
        "checks": [
            (
                "previous",
                "Identify the earlier successful operation in the pack history",
            ),
            (
                "repeat",
                "Confirm the later attempt and whether it came from a retry or a new user action",
            ),
        ],
    },
    "workflow": {
        "label": "Incorrect operational process",
        "hint": "Compare the intended business process with the operation actually submitted and the pack state at that time.",
        "checks": [
            ("intent", "Establish the intended workflow with the End-user"),
            ("operation", "Compare the requested operation and preceding pack state"),
        ],
    },
    "upload": {
        "label": "Missing, late or rejected pack upload",
        "hint": "Check upload timing and outcome. A batch-level upload match does not prove that this individual serial was uploaded.",
        "checks": [
            ("timing", "Compare upload events and outcomes with the exception time"),
            (
                "serial",
                "Check individual pack creation or obtain serial-level evidence from the responsible party",
            ),
        ],
    },
    "master_data": {
        "label": "Product or batch master-data issue",
        "hint": "Compare the values supplied in the transaction with the retained NMVS product/batch data. SAI labels provide Swiss naming context.",
        "checks": [
            ("values", "Compare provided and stored product, batch and expiry values"),
            (
                "owner",
                "Verify the relevant master-data discrepancy with supporting evidence",
            ),
        ],
    },
    "market": {
        "label": "Market or distribution context",
        "hint": "Check the intended market and transaction context. Transaction markets do not establish physical location or prove an unauthorised distribution route.",
        "checks": [
            ("market", "Establish the intended market and relevant product context"),
            ("request", "Compare requesting market, business process and pack history"),
        ],
    },
    "technical": {
        "label": "Technical or interface issue",
        "hint": "Distinguish a system/interface failure from a valid rejection of an invalid operation.",
        "checks": [
            ("logs", "Compare original request/response and relevant interface logs"),
            (
                "incident",
                "Correlate timing with a verified system incident or reproducible defect",
            ),
        ],
    },
    "other": {
        "label": "Other evidenced cause",
        "hint": "Explain why the established categories do not fit. A suspected falsification requires separate escalation and must not be inferred from an alert alone.",
        "checks": [
            (
                "description",
                "Describe the alternative explanation and why the listed categories do not fit",
            ),
            ("evidence", "Identify evidence that supports this explanation"),
        ],
    },
}
CONFIDENCE = {
    "unassessed": "Not yet assessed",
    "suspected": "Working hypothesis",
    "confirmed": "Confirmed by reviewer",
}
CHECKS = {
    "not_checked": "Not checked yet",
    "checked": "Checked",
    "not_applicable": "Not applicable · explain in findings",
}


def parse(data, existing=None):
    if "category" not in data:
        return (
            existing  # Preserve pre-guidance clients and legacy free-text assessments.
        )
    category = data.get("category")
    confidence = data.get("confidence")
    if category not in CATEGORIES or confidence not in CONFIDENCE:
        raise ValueError("Choose a valid cause category and assessment level.")
    if category == "unknown" and confidence != "unassessed":
        raise ValueError("An unknown cause must remain Not yet assessed.")
    checks = {
        key: data.get(f"check_{category}_{key}", "not_checked")
        for key, _ in CATEGORIES[category]["checks"]
    }
    if any(value not in CHECKS for value in checks.values()):
        raise ValueError("Choose a valid result for each investigation check.")
    if confidence == "confirmed":
        if not data.get("cause", "").strip() or not data.get("findings", "").strip():
            raise ValueError(
                "A confirmed cause needs a conclusion and supporting findings/evidence."
            )
        if "not_checked" in checks.values() or "checked" not in checks.values():
            raise ValueError(
                "Complete the relevant checks before confirming a cause. At least one must be Checked."
            )
    return {
        "catalogue_version": 1,
        "category": category,
        "confidence": confidence,
        "checks": checks,
    }


def transferable(review):
    return bool(
        review
        and review.cause.strip()
        and review.review_reason.strip()
        and review.analysis
        and review.analysis.get("category") in CATEGORIES
        and review.analysis.get("category") != "unknown"
        and review.analysis.get("confidence") == "confirmed"
    )
