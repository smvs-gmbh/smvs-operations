import csv
import io
import re
from dataclasses import dataclass

from app.integration.sources.nmvs.parsing import ExtractedDataset
from app.integration.sources.sai.parsing import normalize_gtin14

HEADERS = (
    "Date and Time (UTC)",
    "Process",
    "Transaction ID",
    "Event Code",
    "Event Name",
    "Event Description",
    "Batch Number",
    "Event Message",
    "Event Details",
    "Category",
    "Severity",
)


@dataclass(frozen=True)
class PackAudit:
    file_metadata: dict
    datasets: tuple


def scheme(value):
    return {
        "GTIN": "GTIN",
        "GS1": "GTIN",
        "NTIN": "GTIN",
        "PPN": "PPN",
        "IFA": "PPN",
    }.get(value)


def same_pack(metadata, parameters):
    if scheme(metadata.get("Product Code Scheme")) != scheme(
        parameters["productCodeScheme"]
    ):
        return False
    actual, requested = metadata.get("Product Code"), parameters["productCode"]
    codes_equal = actual == requested
    if not codes_equal and scheme(parameters["productCodeScheme"]) == "GTIN":
        try:
            normalized = normalize_gtin14(actual)
            codes_equal = normalized is not None and normalized == normalize_gtin14(
                requested
            )
        except ValueError:
            codes_equal = False
    return (
        codes_equal and metadata.get("Pack Serial Number") == parameters["serialNumber"]
    )


def parse_pack_audit(content):
    if len(content) > 20_000_000:
        raise ValueError("Pack audit exceeds the size limit.")
    # SSR exports English CSV as UTF-8 or Windows-1252. BOMs take precedence.
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
        raise ValueError("Pack audit metadata is incomplete.")
    metadata = dict(zip(rows[0], rows[1], strict=True))
    if metadata.get("Report Type") != "Pack Audit Trail Report":
        raise ValueError("Unexpected audit report type.")
    if any(
        not metadata.get(k)
        for k in ("Product Code Scheme", "Product Code", "Pack Serial Number")
    ):
        raise ValueError("Pack audit identifiers are incomplete.")
    remaining = [r for r in rows[2:] if r]
    if not remaining or tuple(remaining[0]) != HEADERS:
        raise ValueError("Unexpected pack audit columns.")
    events = []
    for values in remaining[1:]:
        if len(values) != len(HEADERS) or any(len(v) > 100000 for v in values):
            raise ValueError("Invalid pack audit row.")
        events.append(dict(zip(HEADERS, values, strict=True)))
        if len(events) > 20000:
            raise ValueError("Too many pack audit events.")
    # Repeated identical rows are retained; the source has no universal event identity contract.
    return PackAudit(
        metadata, (ExtractedDataset("PackAuditTrail", 1, HEADERS, tuple(events)),)
    )


def details(value):
    """Extract only unambiguous named values; preserve raw text and repeated keys."""
    fields = {}
    for part in (value or "").replace("\\r\\n", "\n").replace("\\n", "\n").split(";"):
        match = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9_ ]*):\s*([\s\S]*?)\s*", part)
        if match:
            fields.setdefault(match[1], []).append(match[2])
    return {k: values[0] for k, values in fields.items() if len(values) == 1}
