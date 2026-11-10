"""Explicit participant projection and source-traceable read-only guidance.

No ORM serialisation, report acquisition, invitations, decisions or writes.
The projection is a draft for NMVO review, not an access grant or publication.
"""

GUIDANCE_VERSION = "emvo-00306-smvs-preview-3"
SOURCE_FINGERPRINT = "696c295b4f41def944935cceeb3cfb5feb776f6bf0c703ef18963d3aea5b9bee"
ERRORS = {
    "A2": (
        "Batch not found",
        "Compare the submitted batch with the pack. SMVS will review available upload evidence.",
    ),
    "A3": (
        "Pack not found",
        "Compare the identifiers and investigate scanning or software discrepancies.",
    ),
    "A7": (
        "Pack already in the requested state",
        "Establish why the operation was requested again and report the findings.",
    ),
    "A24": (
        "Pack state discrepancy",
        "Review the intended operation and prior handling of the pack.",
    ),
    "A52": (
        "Expiry discrepancy",
        "Compare transmitted, stored and printed expiry information.",
    ),
    "A68": (
        "Batch identifier discrepancy",
        "Compare transmitted, stored and printed batch information.",
    ),
}
OPERATIONS = {
    "VERIFIED": "Verify",
    "SUPPLIED": "Supply",
    "EXPORTED": "Export",
    "DESTROYED": "Destroy",
    "STOLEN": "Stolen",
    "SAMPLE": "Sample",
    "FREE_SAMPLE": "Free sample",
    "LOCKED": "Lock",
}


def check(identifier, title, prompt, source, condition=""):
    return {
        "id": identifier,
        "title": title,
        "prompt": prompt,
        "source": source,
        "condition": condition,
    }


def questions(error, workflow):
    result = [
        check(
            "pack-context",
            "Pack and operation",
            "Is the physical pack available, what operation was intended, and what happened immediately before the alert?",
            "3.3 · End-User-01a/01c",
        ),
    ]
    if error in {"A7", "A24"}:
        result += [
            check(
                "procedural",
                "Review the operation",
                "Was this operation requested earlier for the same pack? Report what you can establish from your local workflow and records.",
                "3.3 · End-User-02a",
            ),
            check(
                "different-location",
                "Unexplained earlier handling",
                "If the earlier handling is unknown or may involve another location, ask SMVS to investigate. Do not guess the other location.",
                "3.3 · End-User-02a",
                "If earlier handling is unexplained",
            ),
        ]
    elif error in {"A2", "A3", "A52", "A68"}:
        field = (
            "expiry"
            if error == "A52"
            else "batch"
            if error in {"A2", "A68"}
            else "product, batch and serial"
        )
        result += [
            check(
                "identifier-comparison",
                "Compare the identifiers",
                f"Do the printed {field} values match the values transmitted by your system? Report the comparison and any discrepancy.",
                "3.3 · End-User-01c/01d",
            ),
            check(
                "manual-check",
                "Check whether manual verification adds information",
                "If a permitted manual verification was relevant and performed, report its result. Manual entry is not recommended when scanned and printed values already match; it may produce another alert without new information.",
                "3.3 · End-User-01d",
                "Only where this check adds information under the applicable procedure",
            ),
            check(
                "scanner",
                "Scanner configuration",
                "If a reading discrepancy remains, what scanner configuration checks were performed and what did they show? Report any correction and verification of its effectiveness.",
                "3.3 · End-User-02b",
                "If a procedural cause has not explained the discrepancy",
            ),
            check(
                "software",
                "Software or interface checks",
                "If scanner checks do not explain the discrepancy, record the software/IT investigation, available findings and any further assistance needed.",
                "3.3 · End-User-02c",
                "If scanner error has been ruled out",
            ),
        ]
    else:
        result += [
            check(
                "nmvo-review",
                "Agree the investigation path",
                "Ask SMVS which checks are relevant to this alert. An unsupported error code must not be assigned a cause automatically.",
                "3.1 / 3.8",
            )
        ]
    if workflow == "wholesaler":
        result += [
            check(
                "wholesaler-role",
                "Wholesaler process",
                "Was the operation part of your own process or performed on behalf of another party? Was it an automated job, a bulk operation or a retry? Report relevant local job/software findings.",
                "3.4 / 3.5",
            ),
            check(
                "wholesaler-routing",
                "Communicate the findings",
                "Report pack-state findings to SMVS. A suspected data-upload issue requires coordination with SMVS and the relevant MAH; SMVS will review the appropriate route.",
                "3.4",
            ),
        ]
    result += [
        check(
            "progress",
            "Findings and remaining questions",
            "What have you established, what remains uncertain, and what action has been taken or is still needed? Provide a progress update if your checks are not complete.",
            "3.2 / 3.10",
        )
    ]
    return result


def batch_reference(batch, *, role):
    """Allowlist Snapshot constraints; never interpret an undocumented format code."""
    fields = [
        ("Markets", "Markets"),
        ("Min SN Length", "Minimum serial length"),
        ("Max SN Length", "Maximum serial length"),
        ("SN Format", "Serial format (source code)"),
        ("Batch Length", "Batch length"),
        ("Batch Format", "Batch format (source code)"),
    ]
    evidence = batch.evidence or {}
    return {
        "role": role,
        "batch": batch.batch_code,
        "fields": [
            {"label": label, "value": str(evidence[key])}
            for key, label in fields
            if evidence.get(key) is not None and evidence.get(key) != ""
        ],
    }


def utc(value):
    return value.strftime("%Y-%m-%d %H:%M:%S UTC") if value else "Not available"


def participant_projection(
    record, *, name=None, holder=None, workflow="pharmacy", repeat=None, batches=()
):
    if workflow not in {"pharmacy", "wholesaler"}:
        raise ValueError("Choose pharmacy or wholesaler guidance.")
    label, summary = ERRORS.get(
        record.error_code,
        (
            "Alert requires SMVS review",
            "SMVS will determine the applicable investigation path.",
        ),
    )
    facts = [
        {"label": "Alert reference", "value": record.unique_alert_id or "Not supplied"},
        {"label": "Alert time", "value": utc(record.alert_at)},
        {"label": "Product", "value": name or "Swiss SAI name not available"},
        {
            "label": "Product code",
            "value": record.gtin14 or record.product_code or "Not supplied",
        },
        {"label": "Swiss MAH", "value": holder or "Swiss SAI holder not available"},
        {"label": "Provided batch", "value": record.provided_batch or "Not supplied"},
        {"label": "Stored batch", "value": record.stored_batch or "Not supplied"},
        {
            "label": "Transmitted serial number",
            "value": record.serial_number or "Not supplied",
        },
        {
            "label": "Transmitted serial length",
            "value": str(len(record.serial_number))
            if record.serial_number
            else "Not supplied",
        },
    ]
    operation = OPERATIONS.get((record.evidence or {}).get("attemptedOperation"))
    if operation:
        facts.append({"label": "Attempted operation", "value": operation})
    observed = [
        {
            "at": utc(record.alert_at),
            "label": f"{record.error_code if record.error_code in ERRORS else 'Unclassified'} · {label}",
            "kind": "alert",
        }
    ]
    if repeat:
        # The caller supplies only a sequence already accepted by the existing exact
        # same-pack/same-operation/same-location evaluator. No raw report enters the DTO.
        previous, rejected = repeat["previous"], repeat["repeat"]
        observed = [
            {
                "at": utc(previous["at"]),
                "label": f"Earlier successful {previous['operation']} operation",
                "kind": "observed",
            },
            {
                "at": utc(rejected["at"]),
                "label": f"Rejected repeat {rejected['operation']} operation",
                "kind": "alert",
            },
        ]
    checks = questions(record.error_code, workflow)
    if repeat:
        for question in checks:
            if question["id"] == "procedural":
                question["title"] = "Explain the repeated request"
                question["prompt"] = (
                    "The earlier successful operation and rejected repeat are already documented above. What explains the second request in your process or software? Confirm what local records establish; do not repeat the audit evidence."
                )
    return {
        "schema": "investigation-participant-preview-v3",
        "batch_references": list(batches),
        "assessment": {
            "hypothesis": "A repeated operation may be a procedural error; a software retry or automated job may also explain it.",
            "choices": [
                "Root cause on my side",
                "No root cause identified on my side",
                "Investigation in progress",
            ],
            "known_issue": "Known issue in our process or software",
            "instruction": "Confirm your finding from local records, explain the cause and record corrective action or the next update. Marking an issue as known does not confirm its cause or close this alert.",
        }
        if record.error_code == "A7"
        else None,
        "workflow": workflow,
        "workflow_label": "Wholesaler" if workflow == "wholesaler" else "Pharmacy",
        "title": label,
        "summary": summary,
        "facts": facts,
        "observations": observed,
        "observation_note": "The retained evidence records both operations at the same reported location. The reason for the repeat remains to be investigated."
        if repeat
        else "The source alert is an observation. No cause has been confirmed in this preview.",
        "checks": checks,
        "feedback": "Provide findings or a progress update promptly and within two working days of the alert. SMVS assesses the findings and makes the closure decision.",
        "handling": "Follow the applicable pack-handling procedure. Do not repeat a decommissioning operation simply to collect evidence. An investigation outcome alone does not authorise supply of the pack.",
        "guidance_version": GUIDANCE_VERSION,
    }
