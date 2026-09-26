from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from app.core.http.client import HttpClient, SensitiveHttpError
from app.integration.sources.nmvs.download_uri import (
    DownloadUriError,
    validate_download_uri,
    validate_report_base_url,
)

DAILY_SNAPSHOT_OPERATION_CODE = "15100000"


def utc_day_bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    """Inclusive, second-precision UTC bounds for the selected calendar days."""
    return (
        datetime.combine(from_date, time.min, tzinfo=UTC),
        datetime.combine(to_date, time(23, 59, 59), tzinfo=UTC),
    )


class ReportingApiError(RuntimeError):
    """Raised when the NMVS Reporting API response is unusable."""


@dataclass(frozen=True)
class DailySnapshotResponse:
    report_uri: str
    report_metadata: dict[str, Any]
    content: bytes
    content_type: str | None
    requested_api_version: str | None
    used_api_version: str | None


class ReportingApiClient:
    def __init__(
        self,
        base_url: str,
        token_provider: Callable[[], str],
        api_version: str | None = None,
        http_client: HttpClient | None = None,
    ) -> None:
        validate_report_base_url(base_url)
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._api_version = api_version
        self._http = http_client or HttpClient()

    @property
    def api_version(self) -> str | None:
        return self._api_version

    def close(self) -> None:
        self._http.close()

    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token_provider()}"}
        if self._api_version:
            headers["emvs-api-version"] = self._api_version
        return headers

    def get_daily_snapshot(
        self,
        from_date: date,
        to_date: date,
    ) -> DailySnapshotResponse:
        start, end = utc_day_bounds(from_date, to_date)
        try:
            response = self._http.get_sensitive(
                f"{self._base_url}/report-requests",
                headers=self._headers(),
                params={
                    "fromDate": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "toDate": end.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "reportType": "DailySnapshot",
                },
            )
        except SensitiveHttpError:
            raise ReportingApiError("Report lookup transport failure") from None
        if not 200 <= response.status_code < 300:
            raise ReportingApiError("Report lookup returned an unsuccessful HTTP status")
        try:
            payload = response.json()
        except ValueError:
            raise ReportingApiError("Invalid report lookup response") from None
        if not isinstance(payload, Mapping):
            raise ReportingApiError("Invalid report lookup response")
        if payload.get("operationCode") != DAILY_SNAPSHOT_OPERATION_CODE:
            raise ReportingApiError(
                "Unexpected Daily Snapshot operation code"
            )
        reports = payload.get("reports")
        if not isinstance(reports, list) or len(reports) != 1:
            raise ReportingApiError(
                f"Expected exactly one Daily Snapshot report, received {len(reports) if isinstance(reports, list) else 'invalid'}"
            )
        report = reports[0]
        if not isinstance(report, Mapping) or not report.get("uri"):
            raise ReportingApiError("Daily Snapshot report does not contain a URI")

        try:
            download_uri = validate_download_uri(report["uri"], self._base_url)
        except DownloadUriError as error:
            raise ReportingApiError(str(error)) from None
        try:
            report_response = self._http.get_sensitive(
                download_uri, headers={**self._headers(), "Accept": "text/csv"},
            )
        except SensitiveHttpError:
            raise ReportingApiError("Report download transport failure") from None
        if 300 <= report_response.status_code < 400:
            raise ReportingApiError("Report download redirect refused")
        if not 200 <= report_response.status_code < 300:
            raise ReportingApiError("Report download returned an unsuccessful HTTP status")
        return DailySnapshotResponse(
            report_uri=str(report["uri"]),
            report_metadata=dict(report),
            content=report_response.content,
            content_type=report_response.headers.get("content-type"),
            requested_api_version=self._api_version,
            used_api_version=report_response.headers.get("emvs-api-version"),
        )
