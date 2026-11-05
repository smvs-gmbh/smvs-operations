"""Strict, bounded extraction of the two activity worksheets (UTC calendar days)."""

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from openpyxl import load_workbook

from app.integration.sources.nmvs.parsing import ExtractedDataset

SHEETS = ("Verification", "IMT Fulfilment")
METRIC = re.compile(r"^(\d{4}-\d{2}-\d{2}) (Exception|Total)$")


@dataclass(frozen=True)
class ActivityReport:
    metadata: dict
    start: date
    end: date
    datasets: tuple


def text(value, *, limit=500):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise TypeError("Missing or invalid report dimension.")
    value = str(value)
    if not value or value != value.strip() or len(value) > limit:
        raise ValueError("Missing or invalid report dimension.")
    return value


def count(value, *, average=False):
    # Blank cells are unknown, never silently converted into zero.
    if isinstance(value, bool) or value is None:
        raise ValueError("Missing or invalid activity count.")
    try:
        n = Decimal(str(value))
        if (
            not n.is_finite()
            or (not average and n != n.to_integral_value())
            or not 0 <= n <= 2**63 - 1
        ):
            raise ValueError("Invalid activity count.")
        return str(n) if average else int(n)
    except InvalidOperation:
        raise ValueError("Invalid activity count.") from None


def parse_activity(data: bytes) -> ActivityReport:
    if len(data) > 30_000_000:
        raise ValueError("Activity workbook exceeds size limit.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = archive.infolist()
        if len(files) > 500 or sum(f.file_size for f in files) > 150_000_000:
            raise ValueError("Activity workbook exceeds expansion limit.")
        if any(
            "vbaProject" in f.filename or "externalLinks/" in f.filename for f in files
        ):
            raise ValueError("Workbook contains active or external content.")
    workbook = load_workbook(
        io.BytesIO(data), read_only=True, data_only=False, keep_links=False
    )
    try:
        if any(s not in workbook.sheetnames for s in ("Report Header", *SHEETS)):
            raise ValueError("Activity report worksheets are incomplete.")
        header = workbook["Report Header"]
        if header.max_row > 100 or header.max_column != 2:
            raise ValueError("Invalid report header.")
        metadata = {}
        for name, value in header.iter_rows(values_only=True):
            if name is None:
                continue
            name = text(name)
            if name in metadata:
                raise ValueError("Duplicate report header.")
            metadata[name] = str(value) if value is not None else ""
        if metadata.get("Report Type") != "User Activity Report":
            raise ValueError("Unexpected report type.")
        start, end = (
            date.fromisoformat(metadata[k])
            for k in ("Start Date (UTC)", "End Date (UTC)")
        )
        if end < start or (end - start).days > 365:
            raise ValueError("Invalid activity period.")
        days = [
            (start + timedelta(days=i)).isoformat()
            for i in range((end - start).days + 1)
        ]
        datasets = []
        for order, sheet_name in enumerate(SHEETS, 1):
            sheet = workbook[sheet_name]
            if sheet.max_row > 50000 or sheet.max_column > 740:
                raise ValueError("Activity worksheet exceeds limits.")
            iterator = sheet.iter_rows(values_only=True)
            headers = list(next(iterator))
            dims = (
                [
                    "Organisation Type",
                    "Organisation ID",
                    "Organisation Name",
                    "Business Process",
                ]
                if sheet_name == "Verification"
                else ["Organisation Type", "Market", "Business Process"]
            )
            expected = [f"{d} {m}" for d in days for m in ("Exception", "Total")]
            if headers[: len(dims)] != dims or sorted(headers[len(dims) :]) != sorted(
                expected
            ):
                raise ValueError(
                    "Unexpected activity columns or incomplete date/metric pairs."
                )
            rows, seen = [], set()
            for values in iterator:
                if all(v is None for v in values):
                    continue
                dimensions = {
                    k: text(v, limit=100 if k in ("Organisation ID", "Market") else 500)
                    for k, v in zip(dims, values)
                }
                identity = (
                    dimensions.get("Organisation ID", dimensions.get("Market")),
                    dimensions["Business Process"],
                )
                if identity in seen:
                    raise ValueError(
                        "Duplicate activity dimension; aggregation refused."
                    )
                seen.add(identity)
                metrics = dict(zip(headers[len(dims) :], values[len(dims) :]))
                process = dimensions["Business Process"]
                kind = (
                    "mean_pack_count"
                    if process.endswith(" - Avg. No. Packs")
                    else "pack_count"
                    if process.endswith(" - Total No. Packs")
                    else "transactions"
                )
                for day in days:
                    rows.append(
                        {
                            **dimensions,
                            "Activity Date": day,
                            "Exceptions Count": count(metrics[f"{day} Exception"]),
                            "Count": count(
                                metrics[f"{day} Total"],
                                average=kind == "mean_pack_count",
                            ),
                            "Metric Kind": kind,
                        }
                    )
                    if (
                        kind == "transactions"
                        and rows[-1]["Exceptions Count"] > rows[-1]["Count"]
                    ):
                        raise ValueError("Exception count exceeds transaction count.")
                if len(rows) > 500000:
                    raise ValueError("Too many activity observations.")
            datasets.append(
                ExtractedDataset(
                    source_dataset_name=sheet_name,
                    section_order=order,
                    source_headers=dims
                    + ["Activity Date", "Exceptions Count", "Count", "Metric Kind"],
                    rows=rows,
                )
            )
        return ActivityReport(metadata, start, end, tuple(datasets))
    finally:
        workbook.close()
