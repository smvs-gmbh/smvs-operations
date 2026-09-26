from dataclasses import dataclass
from datetime import date

import pytest

from app.integration.sources.nmvs.reporting import ReportingApiClient


@dataclass
class FakeResponse:
    payload: dict
    status_code: int = 200
    content: bytes = b"artifact"
    headers: dict[str, str] | None = None

    def json(self) -> dict:
        return self.payload


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, dict]] = []
        self.responses = [
            FakeResponse(
                {"operationCode": "15100000", "reports": [{"uri": "https://nmvs.example/reports/daily.csv", "id": "r1"}]}
            ),
            FakeResponse(b"not used" if False else {}, headers={"content-type": "text/csv", "emvs-api-version": "1.0"}),
        ]
        self.responses[1].content = b"csv artifact"

    def get(self, url: str, headers: dict, params: dict | None = None) -> FakeResponse:
        self.calls.append((url, headers, params or {}))
        return self.responses.pop(0)

    def get_sensitive(self, url: str, headers: dict, params: dict | None = None) -> FakeResponse:
        return self.get(url, headers, params)

    def close(self) -> None:
        pass


def test_daily_snapshot_uses_report_requests_and_records_version_headers() -> None:
    http = FakeHttpClient()
    client = ReportingApiClient(
        "https://nmvs.example",
        lambda: "token-not-logged",
        api_version="1.0",
        http_client=http,
    )

    result = client.get_daily_snapshot(date(2026, 9, 25), date(2026, 9, 25))

    assert result.content == b"csv artifact"
    assert http.calls[1][1]["Accept"] == "text/csv"
    assert http.calls[0][0] == "https://nmvs.example/report-requests"
    assert http.calls[0][2] == {
        "fromDate": "2026-09-25T00:00:00Z",
        "toDate": "2026-09-25T23:59:59Z",
        "reportType": "DailySnapshot",
    }
    assert http.calls[0][1]["emvs-api-version"] == "1.0"
    assert result.used_api_version == "1.0"


@pytest.mark.parametrize("day", [date(2025, 6, 15), date(2025, 4, 30), date(2025, 12, 31), date(2024, 2, 29)])
def test_reporting_serializes_exact_utc_day_bounds(day):
    http = FakeHttpClient()
    ReportingApiClient("https://nmvs.example", lambda: "synthetic", http_client=http).get_daily_snapshot(day, day)
    assert http.calls[0][2] == {
        "fromDate": f"{day.isoformat()}T00:00:00Z",
        "toDate": f"{day.isoformat()}T23:59:59Z",
        "reportType": "DailySnapshot",
    }
