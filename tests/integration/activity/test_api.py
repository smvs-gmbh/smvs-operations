from datetime import date
from types import SimpleNamespace

import pytest

from app.integration.sources.nmvs.activity.api import UserActivityClient
from app.integration.sources.nmvs.download_uri import DownloadUriError
from app.integration.sources.nmvs.reporting import ReportingApiError


def response(payload, status=200, content=b"xlsx"):
    return SimpleNamespace(
        status_code=status,
        json=lambda: payload,
        content=content,
        headers={"content-type": "application/xlsx"},
    )


class Http:
    def __init__(
        self,
        *,
        uri="https://example.test/report/reports/ours",
        duplicate=False,
        filter_type="bool",
        late=False,
    ):
        self.uri, self.duplicate, self.filter_type, self.late = (
            uri,
            duplicate,
            filter_type,
            late,
        )
        self.calls = []

    def post_sensitive(self, url, headers, json):
        self.calls.append(("POST", url, headers, json))
        self.name = json["name"]
        return response({"eta": "2026-11-04T14:00:00Z"})

    def get_sensitive(self, url, headers, params=None):
        self.calls.append(("GET", url, headers, params))
        if url.endswith("/report-types/UserActivityReport"):
            return response(
                {
                    "report-type": {
                        "type": "UserActivityReport",
                        "latestAvailableData": "2026-08-01T00:00:00Z"
                        if self.late
                        else "2026-11-04T10:00:00Z",
                        "parameters": [
                            {"id": "syntheticMonitoring", "type": self.filter_type},
                            {"id": "activityDaysOnly", "type": "bool"},
                        ],
                    }
                }
            )
        if url.endswith("/report-requests"):
            ours = {"title": self.name, "uri": self.uri, "status": "Completed"}
            return response(
                {
                    "reports": [
                        {"title": "someone else", "uri": "https://bad.test/stolen"},
                        ours,
                    ]
                    + ([ours] if self.duplicate else [])
                }
            )
        return response({}, content=b"original retained before parsing")


def test_exact_range_exclusions_and_request_correlation():
    http = Http()
    client = UserActivityClient(
        "https://example.test/report", lambda: "test-token", http_client=http
    )
    r = client.get_activity(date(2026, 8, 1), date(2026, 8, 2), pause=lambda _: None)
    post = next(c for c in http.calls if c[0] == "POST")
    assert post[3]["parameters"] == {
        "startDate": "2026-08-01",
        "endDate": "2026-08-02",
        "syntheticMonitoring": False,
        "activityDaysOnly": False,
    }
    assert r.content == b"original retained before parsing"
    assert http.calls[-1][1] == "https://example.test/report/reports/ours"
    assert http.calls[-1][2]["Accept"] == "application/xlsx"
    lookup = next(c for c in http.calls if c[1].endswith("/report-requests"))
    assert (
        lookup[3]["fromDate"][:10] != "2026-08-01"
    )  # Creation window differs from business period.


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"duplicate": True}, ReportingApiError),
        ({"uri": "https://bad.test/report"}, DownloadUriError),
        ({"filter_type": "string"}, ReportingApiError),
        ({"late": True}, ReportingApiError),
    ],
)
def test_ambiguous_or_changed_contract_or_wrong_origin_never_downloaded(kwargs, error):
    http = Http(**kwargs)
    client = UserActivityClient(
        "https://example.test/report", lambda: "test-token", http_client=http
    )
    with pytest.raises(error):
        client.get_activity(date(2026, 8, 1), date(2026, 8, 2), pause=lambda _: None)
    assert all("bad.test" not in c[1] for c in http.calls)
