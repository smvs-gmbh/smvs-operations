import logging
from datetime import date
from unittest.mock import Mock

import httpx
import pytest

from app.core.http.client import HttpClient
from app.integration.sources.nmvs.download_uri import (
    DownloadUriError,
    validate_download_uri,
)
from app.integration.sources.nmvs.reporting import ReportingApiClient, ReportingApiError

BASE = "https://reports.example.test"
TOKEN = "fictional-bearer-value"


def report_client(uri, *, status=200, fail=False):
    calls = []

    def handle(request):
        calls.append(request)
        logging.getLogger("httpcore.http11").debug("headers %s URL %s", request.headers, request.url)
        if request.url.path == "/report-requests":
            return httpx.Response(200, json={"operationCode": "15100000", "reports": [{"uri": uri}]})
        # Simulate transport diagnostics, including sensitive header material.
        logging.getLogger("httpcore.http11").debug("headers %s URL %s", request.headers, request.url)
        if fail:
            raise httpx.ConnectError(f"Untrusted details {uri} {TOKEN}", request=request)
        return httpx.Response(status, headers={"content-type": "text/csv", "location": "https://foreign.test/?key=hidden"}, content=b"synthetic")

    http = HttpClient()
    http._client.close()
    # Even if the injected client's default enables redirects, this request must not.
    http._client = httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=True)
    token_provider = Mock(return_value=TOKEN)
    return ReportingApiClient(BASE, token_provider, http_client=http), calls, token_provider


@pytest.mark.parametrize("uri", [BASE + "/file", BASE + ":443/file", "https://REPORTS.EXAMPLE.TEST/file",
                                BASE + "/file?signature=synthetic-secret"])
def test_accepted_download_gets_bearer_without_sensitive_logs(uri, caplog):
    caplog.set_level(logging.DEBUG)
    client, calls, tokens = report_client(uri)
    try:
        result = client.get_daily_snapshot(date(2024, 1, 1), date(2024, 1, 1))
        assert result.content == b"synthetic"
        assert len(calls) == tokens.call_count == 2
        assert calls[1].headers["Authorization"] == f"Bearer {TOKEN}"
        assert calls[1].headers["Accept"] == "text/csv"
        assert calls[1].url.host == "reports.example.test"
        assert calls[1].url.port in (None, 443)
        if "?" in uri:
            assert calls[1].url.query == b"signature=synthetic-secret"
        assert TOKEN not in caplog.text and "synthetic-secret" not in caplog.text
        assert "/file" not in caplog.text
        logging.getLogger("httpx").info("unrelated diagnostic survives")
        assert "unrelated diagnostic survives" in caplog.text
    finally:
        client.close()


@pytest.mark.parametrize("uri", [
    "http://reports.example.test/file", "https://foreign.test/file",
    "https://reports.example.test.foreign.test/file", "https://user@reports.example.test/file",
    "https://:password@reports.example.test/file", "https://@reports.example.test/file",
    BASE + ":444/file", BASE + ":0/file", BASE + ":99999/file", BASE + ":bad/file", BASE + ":/file",
    "/file", "//reports.example.test/file", "https:///file", "https://", "https://[broken/file",
    BASE + "/file#fragment", BASE + "/file#", BASE + "/file\\other", BASE + "/file%xy",
    " https://reports.example.test/file", BASE + "/file\nheader", "https://%72eports.example.test/file",
    {"not": "a URI"},
])
def test_rejected_uri_never_gets_download_token_or_request(uri, caplog):
    caplog.set_level(logging.DEBUG)
    client, calls, tokens = report_client(uri)
    try:
        with pytest.raises(ReportingApiError) as failure:
            client.get_daily_snapshot(date(2024, 1, 1), date(2024, 1, 1))
        assert len(calls) == tokens.call_count == 1  # Only the approved API lookup.
        assert calls[0].url.path == "/report-requests"
        assert TOKEN not in str(failure.value) + caplog.text
        assert "password" not in str(failure.value) + caplog.text
    finally:
        client.close()


@pytest.mark.parametrize("status", [300, 301, 302, 303, 304, 305, 306, 307, 308, 400, 500])
def test_redirect_and_http_errors_are_sanitized_and_not_followed(status, caplog):
    caplog.set_level(logging.DEBUG)
    client, calls, _ = report_client(BASE + "/file?signature=synthetic-secret", status=status)
    try:
        with pytest.raises(ReportingApiError) as failure:
            client.get_daily_snapshot(date(2024, 1, 1), date(2024, 1, 1))
        assert len(calls) == 2
        if status < 400:
            assert "redirect" in str(failure.value)
        assert all(value not in str(failure.value) + caplog.text
                   for value in (TOKEN, "synthetic-secret", "foreign.test", "hidden"))
    finally:
        client.close()


def test_transport_failure_and_rejected_query_are_sanitized(caplog):
    caplog.set_level(logging.DEBUG)
    client, _calls, _ = report_client(BASE + "/file?signature=synthetic-secret", fail=True)
    try:
        with pytest.raises(ReportingApiError, match="transport failure") as failure:
            client.get_daily_snapshot(date(2024, 1, 1), date(2024, 1, 1))
        assert failure.value.__suppress_context__
        assert TOKEN not in str(failure.value) + caplog.text
        assert "synthetic-secret" not in str(failure.value) + caplog.text
    finally:
        client.close()
    with pytest.raises(DownloadUriError) as failure:
        validate_download_uri("https://foreign.test/file?signature=synthetic-secret", BASE)
    assert "synthetic-secret" not in str(failure.value)


def test_origin_normalizes_configured_default_port():
    assert validate_download_uri(BASE + "/file", BASE + ":443") == BASE + "/file"


@pytest.mark.parametrize("base", ["http://reports.example.test", "https://user@reports.example.test",
                                 "https://reports.example.test?secret=hidden", "https://reports.example.test#fragment"])
def test_invalid_configured_base_fails_before_token_or_http_access(base):
    token = Mock()
    http = Mock()
    with pytest.raises(DownloadUriError):
        ReportingApiClient(base, token, http_client=http)
    token.assert_not_called()
    assert http.mock_calls == []
