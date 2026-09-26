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
    report_metadata: dict[str, str]
    datasets: tuple[ExtractedDataset, ...]


def parse_daily_snapshot(content: bytes) -> ParsedDailySnapshot:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DailySnapshotParseError("Daily Snapshot is not valid UTF-8") from exc

    sections = _split_sections(text)
    if not sections:
        raise DailySnapshotParseError("Daily Snapshot is empty")
    metadata = _parse_metadata(sections[0])
    datasets = tuple(
        _parse_dataset(section, section_order)
        for section_order, section in enumerate(sections[1:], start=1)
        if section.strip()
    )
    return ParsedDailySnapshot(report_metadata=metadata, datasets=datasets)


def _split_sections(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n")
    return normalized.split("\n\n")


def _parse_metadata(section: str) -> dict[str, str]:
    rows = list(csv.reader(io.StringIO(section)))
    if not rows:
        raise DailySnapshotParseError("Missing report metadata section")
    metadata: dict[str, str] = {}
    for row in rows:
        if len(row) < 2 or not row[0].strip():
            raise DailySnapshotParseError("Malformed report metadata row")
        metadata[row[0].strip()] = row[1].strip()
    return metadata


def _parse_dataset(section: str, section_order: int) -> ExtractedDataset:
    lines = section.strip().splitlines()
    if len(lines) < 2 or not lines[0].strip():
        raise DailySnapshotParseError("Malformed dataset section")
    dataset_name = lines[0].strip()
    rows = list(csv.reader(io.StringIO("\n".join(lines[1:]))))
    if not rows or not rows[0]:
        raise DailySnapshotParseError(f"Dataset {dataset_name!r} has no header")
    headers = tuple(rows[0])
    records: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row:
            continue
        values = row[: len(headers)]
        record = {header: values[index] if index < len(values) else None for index, header in enumerate(headers)}
        if len(row) > len(headers):
            record["__extra__"] = row[len(headers) :]
        records.append(record)
    return ExtractedDataset(
        source_dataset_name=dataset_name,
        section_order=section_order,
        source_headers=headers,
        rows=tuple(records),
    )


def record_hash(record: dict[str, Any]) -> str:
    encoded = repr(sorted(record.items())).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
