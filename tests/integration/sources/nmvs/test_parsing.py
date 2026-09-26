import pytest

from app.integration.sources.nmvs.parsing import (
    DailySnapshotParseError,
    parse_daily_snapshot,
)


def test_discovers_datasets_and_preserves_empty_sections_and_extra_fields() -> None:
    content = (
        b"Report Type,DailySnapshot\r\n"
        b"Report Name,Daily Snapshot\r\n"
        b"Date Requested (UTC),2026-09-25T00:00:00Z\r\n\r\n"
        b"Products\r\n"
        b"Product Code,Product State\r\n"
        b"001,Active,unexpected\r\n\r\n"
        b"Empty Dataset\r\n"
        b"A,B\r\n"
        b"\r\n\r\n"
        b"New Dataset\r\n"
        b"Field\r\n"
        b"value\r\n"
    )

    parsed = parse_daily_snapshot(content)

    assert parsed.report_metadata["Report Type"] == "DailySnapshot"
    assert [dataset.source_dataset_name for dataset in parsed.datasets] == [
        "Products",
        "Empty Dataset",
        "New Dataset",
    ]
    assert parsed.datasets[0].rows[0]["__extra__"] == ["unexpected"]
    assert parsed.datasets[1].rows == ()
    assert parsed.datasets[2].rows[0] == {"Field": "value"}


def test_rejects_malformed_metadata() -> None:
    with pytest.raises(DailySnapshotParseError):
        parse_daily_snapshot(b"not metadata\n\nProducts\nA\nvalue\n")
