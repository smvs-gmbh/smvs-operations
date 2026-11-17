"""Strict source validation; coverage is recorded only for accepted genuine reports."""

import csv
import io
from datetime import UTC, datetime

from app.integration.sources.nmvs.pack_audit.parsing import PackAudit
from app.integration.sources.nmvs.parsing import ExtractedDataset

HEADERS = (
    "Date and Time (UTC)",
    "Event Name",
    "Event Description",
    "Transaction ID",
    "Product Code Scheme",
    "Product Code",
    "Process",
    "Event Details",
    "Category",
    "Severity",
)


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("An explicit UTC offset is required.")
    return parsed.astimezone(UTC).replace(tzinfo=None)


def parse_upload(content):
    if len(content) > 40_000_000:
        raise ValueError("Upload report exceeds size limit.")
    try:
        encoding = (
            "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        )
        text = content.decode(encoding)
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    if (
        len(rows) < 4
        or len(rows[0]) != len(rows[1])
        or len(set(rows[0])) != len(rows[0])
    ):
        raise ValueError("Invalid upload metadata.")
    metadata = dict(zip(rows[0], rows[1], strict=True))
    if metadata.get("Report Type") != "Product Pack Upload Audit Trail Report":
        raise ValueError("Wrong report type.")
    if metadata.get("Synthetic Monitoring") != "Genuine Transactions":
        raise ValueError("Genuine-transactions filter was not confirmed by the source.")
    start, end = (
        instant(metadata[k])
        for k in ("Start Date & Time (UTC)", "End Date & Time (UTC)")
    )
    if start >= end:
        raise ValueError("Invalid upload period.")
    remaining = [r for r in rows[2:] if r]
    if not remaining or tuple(remaining[0]) != HEADERS:
        raise ValueError("Upload columns changed.")
    events = []
    for values in remaining[1:]:
        if len(values) != len(HEADERS) or any(len(v) > 100000 for v in values):
            raise ValueError("Invalid upload row.")
        row = dict(zip(HEADERS, values, strict=True))
        if not start <= instant(row["Date and Time (UTC)"]) <= end:
            raise ValueError("Upload event outside the report period.")
        events.append(row)
        if len(events) > 100000:
            raise ValueError("Too many upload events.")
    return PackAudit(
        metadata, (ExtractedDataset("ProductPackUpload", 1, HEADERS, tuple(events)),)
    )
