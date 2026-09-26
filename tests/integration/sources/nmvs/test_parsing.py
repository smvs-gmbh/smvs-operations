import csv
import io

import pytest

from app.integration.sources.nmvs.parsing import (
    DailySnapshotParseError,
    parse_daily_snapshot,
    validate_csv_content_type,
)

UNICODE = 'ä ö ü Ä Ö Ü é è à ç Ελληνικά \u00a0 \u200b Â® Ã¶'


def report_bytes(*sections, extra_metadata=False):
    """Fictional values only; the fully quoted grammar observed in the source."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    headers = ["Report Type", "Report Name", "Date Requested (UTC)"]
    values = ["Daily Snapshot", "Synthetic", "2024-02-29T00:00:00Z"]
    if extra_metadata:
        headers.append("Additional Column")
        values.append(" preserved ")
    writer.writerows([headers, values])
    for section in sections:
        writer.writerow([])
        writer.writerows(section)
    return stream.getvalue().encode("utf-8")


def test_observed_grammar_preserves_values_names_order_and_empty_datasets():
    values = [UNICODE, 'comma, and "quotes"', 'LF\nline', 'CRLF\r\nline',
              'blank\r\n\r\nline', '  edge whitespace \t', 'Unicode\u2028separator\u2029retained']
    content = report_bytes(
        [[" First Dataset "], ["Second", "First"], *[[str(i), value] for i, value in enumerate(values)]],
        [["Empty Dataset"], ["B", "A"]],
        [["Last Dataset"], ["__extra__"], ["legitimate source field"], [""]],
        extra_metadata=True,
    )
    parsed = parse_daily_snapshot(content)
    assert parsed.file_metadata == {
        "Report Type": "Daily Snapshot", "Report Name": "Synthetic",
        "Date Requested (UTC)": "2024-02-29T00:00:00Z", "Additional Column": " preserved ",
    }
    assert list(parsed.file_metadata) == ["Report Type", "Report Name", "Date Requested (UTC)", "Additional Column"]
    assert [d.source_dataset_name for d in parsed.datasets] == [" First Dataset ", "Empty Dataset", "Last Dataset"]
    assert [d.section_order for d in parsed.datasets] == [1, 2, 3]
    assert parsed.datasets[0].source_headers == ("Second", "First")
    assert parsed.datasets[0].rows == tuple({"Second": str(i), "First": value} for i, value in enumerate(values))
    assert parsed.datasets[1].source_headers == ("B", "A")
    assert parsed.datasets[1].rows == ()
    assert parsed.datasets[2].rows == ({"__extra__": "legitimate source field"}, {"__extra__": ""})
    assert content.decode("utf-8").encode("utf-8") == content


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_strict_utf8_with_optional_bom_and_no_repair(bom):
    parsed = parse_daily_snapshot(bom + report_bytes([["Data"], ["Value"], [UNICODE]]))
    assert parsed.datasets[0].rows == ({"Value": UNICODE},)


@pytest.mark.parametrize("section", [
    [["Data"], ["A", "A"], ["1", "2"]],
    [["Data"], ["A"], ["1", "2"]],
    [["Data"], ["A", "B"], ["1"]],
    [["Data", "ambiguous"], ["A"]],
    [["Data"]],
    [[""] , ["A"]],
    [["Data"], [""]],
])
def test_rejects_ambiguous_dataset_structure(section):
    with pytest.raises(DailySnapshotParseError):
        parse_daily_snapshot(report_bytes(section))


@pytest.mark.parametrize("tail", [b'"unfinished', b'"closed"garbage\r\n', b'bare"quote\r\n'])
def test_rejects_malformed_quotes(tail):
    with pytest.raises(DailySnapshotParseError):
        parse_daily_snapshot(report_bytes([["Data"], ["A"]]) + tail)


def test_rejects_invalid_utf8():
    with pytest.raises(DailySnapshotParseError, match="UTF-8"):
        parse_daily_snapshot(report_bytes([["Data"], ["A"]]) + b'"\xff"\r\n')


def test_rejects_metadata_only_report():
    with pytest.raises(DailySnapshotParseError, match="no datasets"):
        parse_daily_snapshot(report_bytes())


@pytest.mark.parametrize("metadata", [
    b'',
    b'"Report Type","Report Type"\r\n"a","b"\r\n',
    b'"Report Type","Report Name","Date Requested (UTC)"\r\n"a","b"\r\n',
    b'"Report Type","Report Name","Date Requested (UTC)"\r\n"a","b","c","d"\r\n',
    b'"Report Type","Report Name","Date Requested (UTC)"\r\n"a","b","c"\r\n"d","e","f"\r\n',
    b'"Unknown"\r\n"value"\r\n',
])
def test_rejects_ambiguous_metadata(metadata):
    with pytest.raises(DailySnapshotParseError):
        parse_daily_snapshot(metadata + b'\r\n"Data"\r\n"A"\r\n')


def test_rejects_duplicate_dataset_names():
    with pytest.raises(DailySnapshotParseError, match="Duplicate dataset"):
        parse_daily_snapshot(report_bytes([["Data"], ["A"]], [["Data"], ["B"]]))


@pytest.mark.parametrize("content_type", ["text/csv", "TEXT/CSV", 'text/csv; charset="utf-8"',
                                        "text/csv; charset=UTF-8; header=present"])
def test_accepts_csv_media_type_parameters(content_type):
    validate_csv_content_type(content_type)


@pytest.mark.parametrize("content_type", [None, "", "text/plain", "application/json", "text/csv-other",
                                        "text/csv, text/html", "text/csv; broken", 'text/csv; charset="unfinished',
                                        "text/csv\r\nX-Fake: value"])
def test_rejects_missing_unrelated_or_malformed_media_type(content_type):
    with pytest.raises(DailySnapshotParseError, match="Content-Type"):
        validate_csv_content_type(content_type)
