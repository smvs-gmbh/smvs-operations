from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from typing import Any


class DailySnapshotParseError(ValueError):
    """Raised when the Daily Snapshot structure cannot be parsed."""


@dataclass(frozen=True)
class ExtractedDataset:
    source_dataset_name: str
    section_order: int
    source_headers: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ParsedDailySnapshot:
    # Ordered CSV column/value mapping, distinct from acquisition API metadata.
    file_metadata: dict[str, str]
    datasets: tuple[ExtractedDataset, ...]


def parse_daily_snapshot(content: bytes) -> ParsedDailySnapshot:
    try:
        text = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise DailySnapshotParseError("Daily Snapshot is not valid UTF-8") from None

    _reject_bare_quotes(text)
    sections: list[list[list[str]]] = []
    section: list[list[str]] = []
    try:
        # newline='' leaves embedded LF/CRLF untouched. Only an empty *logical*
        # record separates sections; quoted empty fields and blank lines are data.
        for row in csv.reader(io.StringIO(text, newline=""), strict=True):
            if row:
                section.append(row)
            elif section:
                sections.append(section)
                section = []
    except csv.Error:
        raise DailySnapshotParseError("Malformed Daily Snapshot CSV") from None
    if section:
        sections.append(section)
    if not sections:
        raise DailySnapshotParseError("Daily Snapshot is empty")
    metadata = _parse_metadata(sections[0])
    if len(sections) < 2:
        raise DailySnapshotParseError("Daily Snapshot contains no datasets")
    datasets = tuple(_parse_dataset(rows, order) for order, rows in enumerate(sections[1:], 1))
    names = [dataset.source_dataset_name for dataset in datasets]
    if len(set(names)) != len(names):
        raise DailySnapshotParseError("Duplicate dataset names")
    return ParsedDailySnapshot(file_metadata=metadata, datasets=datasets)


def _reject_bare_quotes(text: str) -> None:
    """csv strict mode still accepts quotes inside unquoted fields; reject those."""
    state = "start"
    for char in text:
        if state == "quoted":
            if char == '"':
                state = "closed"
        elif state == "closed":
            if char == '"':
                state = "quoted"  # CSV doubled quote.
            elif char in ",\r\n":
                state = "start"
            else:
                raise DailySnapshotParseError("Malformed Daily Snapshot CSV quoting")
        elif char == '"':
            if state != "start":
                raise DailySnapshotParseError("Quote inside an unquoted CSV field")
            state = "quoted"
        elif char in ",\r\n":
            state = "start"
        else:
            state = "unquoted"
    if state == "quoted":
        raise DailySnapshotParseError("Unclosed Daily Snapshot CSV quote")


def _headers(row: list[str]) -> tuple[str, ...]:
    if not row or any(not value or value.isspace() for value in row):
        raise DailySnapshotParseError("Missing or empty CSV header")
    if len(set(row)) != len(row):
        raise DailySnapshotParseError("Duplicate CSV headers")
    return tuple(row)


def _record(headers: tuple[str, ...], row: list[str]) -> dict[str, str]:
    if len(row) != len(headers):
        raise DailySnapshotParseError("CSV row width does not match its headers")
    return dict(zip(headers, row, strict=True))


def _parse_metadata(rows: list[list[str]]) -> dict[str, str]:
    if len(rows) != 2:
        raise DailySnapshotParseError("Report metadata must contain one header and one value record")
    headers = _headers(rows[0])
    if not {"Report Type", "Report Name", "Date Requested (UTC)"}.issubset(headers):
        raise DailySnapshotParseError("Missing required report metadata columns")
    return _record(headers, rows[1])


def _parse_dataset(rows: list[list[str]], section_order: int) -> ExtractedDataset:
    if len(rows) < 2 or len(rows[0]) != 1 or not rows[0][0] or rows[0][0].isspace():
        raise DailySnapshotParseError("Dataset requires one name field and a header record")
    headers = _headers(rows[1])
    return ExtractedDataset(
        source_dataset_name=rows[0][0],
        section_order=section_order,
        source_headers=headers,
        rows=tuple(_record(headers, row) for row in rows[2:]),
    )


def record_hash(record: dict[str, Any]) -> str:
    encoded = repr(sorted(record.items())).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
