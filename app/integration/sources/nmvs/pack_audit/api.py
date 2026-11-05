import time
from datetime import UTC, datetime, timedelta

from app.integration.sources.nmvs.activity.api import UserActivityClient
from app.integration.sources.nmvs.download_uri import validate_download_uri
from app.integration.sources.nmvs.reporting import (
    DailySnapshotResponse,
    ReportingApiError,
)


class PackAuditClient(UserActivityClient):
    report_type = "PackAuditTrailReport"
    required_parameters = frozenset(
        {"productCodeScheme", "productCode", "serialNumber"}
    )

    def definition(self):
        r = self._http.get_sensitive(
            self._base_url + "/report-types/" + self.report_type,
            headers=self._headers(),
        )
        if r.status_code != 200:
            raise ReportingApiError("Pack report definition unavailable.")
        d = r.json().get("report-type", {})
        required = {p.get("id") for p in d.get("parameters", []) if p.get("mandatory")}
        if d.get("type") != self.report_type or required != self.required_parameters:
            raise ReportingApiError("Pack report contract changed.")
        return d

    def get_pack(self, parameters, *, title, created_at, timeout=600, pause=time.sleep):
        definition = self.definition()
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        deadline = time.monotonic() + timeout
        submitted = False
        while time.monotonic() < deadline:
            response = self._http.get_sensitive(
                self._base_url + "/report-requests",
                headers=self._headers(),
                params={
                    "fromDate": (created_at - timedelta(seconds=5))
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "toDate": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "reportType": self.report_type,
                    "requestedBy": "SMVS Operations",
                },
            )
            if response.status_code != 200:
                raise ReportingApiError("Pack report lookup failed.")
            reports = response.json().get("reports", [])
            if not isinstance(reports, list) or any(
                not isinstance(r, dict) for r in reports
            ):
                raise ReportingApiError("Invalid pack lookup.")
            matches = [r for r in reports if r.get("title") == title]
            if len(matches) > 1:
                raise ReportingApiError("Ambiguous pack report request.")
            if not matches and not submitted:
                response = self._http.post_sensitive(
                    self._base_url + "/report-request",
                    headers=self._headers(),
                    json={
                        "report Type Id": self.report_type,
                        "name": title,
                        "requested By": "SMVS Operations",
                        "parameters": parameters,
                    },
                )
                if not 200 <= response.status_code < 300:
                    raise ReportingApiError("Pack report request rejected.")
                submitted = True
            if matches:
                report = matches[0]
                if report.get("status") in ("Failed", "Error", "Cancelled"):
                    raise ReportingApiError("Pack report generation failed.")
                if report.get("uri"):
                    uri = validate_download_uri(report["uri"], self._base_url)
                    r = self._http.get_sensitive(
                        uri, headers={**self._headers(), "Accept": "text/csv"}
                    )
                    if r.status_code == 200:
                        return DailySnapshotResponse(
                            uri,
                            {
                                "request": parameters,
                                "report": report,
                                "data_available_at_request": definition.get(
                                    "latestAvailableData"
                                ),
                            },
                            r.content,
                            r.headers.get("content-type"),
                            self.api_version,
                            r.headers.get("emvs-api-version"),
                        )
                    if (
                        r.status_code != 409
                        or r.json().get("operationCode") != "55420000"
                    ):
                        raise ReportingApiError("Pack report download failed.")
            pause(min(5, max(0, deadline - time.monotonic())))
        raise ReportingApiError("Pack report readiness timed out.")
