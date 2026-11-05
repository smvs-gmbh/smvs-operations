import time
import uuid
from datetime import UTC, date, datetime, timedelta

from app.integration.sources.nmvs.download_uri import validate_download_uri
from app.integration.sources.nmvs.reporting import (
    DailySnapshotResponse,
    ReportingApiClient,
    ReportingApiError,
)


class UserActivityClient(ReportingApiClient):
    def _headers(self):
        return {
            **super()._headers(),
            "Accept-Language": "en",
            "User-Agent": getattr(self, "user_agent", "SMVS Operations"),
        }

    def definition(self):
        response = self._http.get_sensitive(
            f"{self._base_url}/report-types/UserActivityReport", headers=self._headers()
        )
        if response.status_code != 200:
            raise ReportingApiError("Activity report definition unavailable.")
        definition = response.json().get("report-type", {})
        parameters = {
            p.get("id"): p.get("type") for p in definition.get("parameters", [])
        }
        if (
            definition.get("type") != "UserActivityReport"
            or parameters.get("syntheticMonitoring") != "bool"
            or parameters.get("activityDaysOnly") != "bool"
        ):
            raise ReportingApiError("Activity report filter contract changed.")
        return definition

    def get_activity(self, start: date, end: date, *, timeout=600, pause=time.sleep):
        if end < start or end >= datetime.now(UTC).date():
            raise ValueError("Only complete UTC days may be requested.")
        definition = self.definition()
        latest = datetime.fromisoformat(
            definition["latestAvailableData"].replace("Z", "+00:00")
        )
        if latest < datetime.combine(
            end + timedelta(days=1), datetime.min.time(), tzinfo=UTC
        ):
            raise ReportingApiError("Source has not completed the requested UTC day.")
        created = datetime.now(UTC)
        name = "SMVS Operations " + uuid.uuid4().hex
        parameters = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "syntheticMonitoring": False,
            "activityDaysOnly": False,
        }
        response = self._http.post_sensitive(
            f"{self._base_url}/report-request",
            headers=self._headers(),
            json={
                "report Type Id": "UserActivityReport",
                "name": name,
                "requested By": "SMVS Operations",
                "parameters": parameters,
            },
        )
        if not 200 <= response.status_code < 300:
            raise ReportingApiError("Activity report request failed.")
        posted = response.json()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self._http.get_sensitive(
                f"{self._base_url}/report-requests",
                headers=self._headers(),
                params={
                    "fromDate": (created - timedelta(seconds=5))
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "toDate": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "reportType": "UserActivityReport",
                    "requestedBy": "SMVS Operations",
                },
            )
            if response.status_code not in (200, 409):
                raise ReportingApiError("Activity report lookup failed.")
            payload = response.json()
            if (
                response.status_code == 409
                and payload.get("operationCode") != "55420000"
            ):
                raise ReportingApiError("Unexpected activity readiness response.")
            reports = payload.get("reports", [])
            if not isinstance(reports, list) or any(
                not isinstance(r, dict) for r in reports
            ):
                raise ReportingApiError("Invalid activity report lookup response.")
            # Unique generated name, never pick an arbitrary concurrent request.
            matches = [r for r in reports if r.get("title") == name]
            if len(matches) > 1:
                raise ReportingApiError("Ambiguous activity report identity.")
            if matches and matches[0].get("status") in ("Failed", "Error", "Cancelled"):
                raise ReportingApiError("Source could not generate activity report.")
            if matches and matches[0].get("uri"):
                report = matches[0]
                uri = validate_download_uri(report["uri"], self._base_url)
                download = self._http.get_sensitive(
                    uri, headers={**self._headers(), "Accept": "application/xlsx"}
                )
                if download.status_code == 200:
                    return DailySnapshotResponse(
                        uri,
                        {
                            "report": report,
                            "request": parameters,
                            "request_response": posted,
                        },
                        download.content,
                        download.headers.get("content-type"),
                        self.api_version,
                        download.headers.get("emvs-api-version"),
                    )
                if (
                    download.status_code == 409
                    and download.json().get("operationCode") != "55420000"
                ):
                    raise ReportingApiError(
                        "Unexpected activity download readiness response."
                    )
                if download.status_code != 409:
                    raise ReportingApiError("Activity report download failed.")
            pause(min(10, max(0, deadline - time.monotonic())))
        raise ReportingApiError("Activity report readiness timed out.")
