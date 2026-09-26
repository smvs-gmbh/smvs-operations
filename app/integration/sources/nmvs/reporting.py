from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.core.http.client import HttpClient

DAILY_SNAPSHOT_OPERATION_CODE = "15100000"


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
        response = self._http.get(
            f"{self._base_url}/report-requests",
            headers=self._headers(),
            params={
                "fromDate": from_date.isoformat(),
                "toDate": to_date.isoformat(),
                "reportType": "DailySnapshot",
            },
        )
        payload = response.json()
        if payload.get("operationCode") != DAILY_SNAPSHOT_OPERATION_CODE:
            raise ReportingApiError(
                f"Unexpected Daily Snapshot operation code: {payload.get('operationCode')}"
            )
        reports = payload.get("reports")
        if not isinstance(reports, list) or len(reports) != 1:
            raise ReportingApiError(
                f"Expected exactly one Daily Snapshot report, received {len(reports) if isinstance(reports, list) else 'invalid'}"
            )
        report = reports[0]
        if not isinstance(report, Mapping) or not report.get("uri"):
            raise ReportingApiError("Daily Snapshot report does not contain a URI")

        report_response = self._http.get(
            self._absolute_uri(str(report["uri"])),
            headers=self._headers(),
        )
        return DailySnapshotResponse(
            report_uri=str(report["uri"]),
            report_metadata=dict(report),
            content=report_response.content,
            content_type=report_response.headers.get("content-type"),
            requested_api_version=self._api_version,
            used_api_version=report_response.headers.get("emvs-api-version"),
        )

    def _absolute_uri(self, uri: str) -> str:
        if uri.startswith(("http://", "https://")):
            return uri
        return f"{self._base_url}/{uri.lstrip('/')}"
