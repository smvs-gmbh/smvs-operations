import re
import time
from datetime import UTC, timedelta

from app.integration.sources.nmvs.reporting import ReportingApiClient


class ExceptionsApiError(ValueError):
    pass


def window(start, end):
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or end < start
        or end - start > timedelta(days=31)
    ):
        raise ValueError("An explicit UTC query window of at most 31 days is required.")
    return {
        "startTimestamp": start.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "endTimestamp": end.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }


class ExceptionsClient(ReportingApiClient):
    def _headers(self):
        return {
            **super()._headers(),
            "User-Agent": getattr(self, "user_agent", "SMVS Operations"),
            "Accept-Language": "en",
            "Accept": "application/json",
        }

    def request(self, start, end):
        parameters = window(start, end)
        response = self._http.post_sensitive(
            self._base_url + "/alerts", headers=self._headers(), json=parameters
        )
        if response.status_code != 202:
            raise ExceptionsApiError("Exception query was not accepted.")
        return self.query_id(response.json().get("requestID")), parameters

    @staticmethod
    def query_id(value):
        if not isinstance(value, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", value
        ):
            raise ExceptionsApiError("Invalid exception query identifier.")
        return value

    def escalate(self, request_id):
        request_id = self.query_id(request_id)
        response = self._http.post_sensitive(
            self._base_url + "/alerts/fulldataset/" + request_id,
            headers=self._headers(),
            json=None,
        )
        if response.status_code != 202:
            raise ExceptionsApiError("Exception full dataset query was not accepted.")
        return self.query_id(response.json().get("requestID"))

    def page(self, request_id, page, *, pause=time.sleep, timeout=600):
        request_id = self.query_id(request_id)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self._http.get_sensitive(
                self._base_url + "/alerts/data/" + request_id,
                headers=self._headers(),
                params={"page": str(page), "pageSize": "1000"},
            )
            if response.status_code == 200:
                return response
            if response.status_code != 409:
                raise ExceptionsApiError("Exception query data could not be read.")
            pause(min(5, max(0, deadline - time.monotonic())))
        raise ExceptionsApiError("Exception query readiness timed out.")
