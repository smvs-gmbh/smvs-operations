from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.alert_desk.settings import AlertDeskSettings
from app.alert_desk.web import ACCESS_COOKIE, create_app
from app.portal import collaboration_routes


@pytest.mark.parametrize("environment,enabled,allowed", [
    ("development", False, True), ("test", False, False),
    ("test", True, True), ("production", True, False), ("other", True, False),
])
def test_hosted_feature_gate_does_not_enable_production(monkeypatch, environment, enabled, allowed):
    settings = AlertDeskSettings(environment=environment, alert_desk_test_enabled=enabled)
    if allowed:
        settings.require_enabled()
    else:
        with pytest.raises(RuntimeError):
            settings.require_enabled()
    monkeypatch.setattr(collaboration_routes, "get_settings", lambda: SimpleNamespace(
        environment=environment, alert_desk_test_enabled=enabled,
    ))
    monkeypatch.setenv("ALERT_DESK_PILOT_SECRET", "test-only-secret-" * 3)
    assert collaboration_routes.pilot_enabled() == allowed
    monkeypatch.delenv("ALERT_DESK_PILOT_SECRET")
    assert not collaboration_routes.pilot_enabled()


@pytest.mark.parametrize("public,private", [
    ("http://external.example", "http://127.0.0.1:8017"),
    ("https://example.test/path", "http://127.0.0.1:8017"),
    ("https://user:pass@example.test", "http://127.0.0.1:8017"),
    ("https://example.test?next=1", "http://127.0.0.1:8017"),
    ("https://example.test#token", "http://127.0.0.1:8017"),
    ("https://example.test", "http://external.example"),
    ("https://example.test", "http://127.0.0.1:bad"),
])
def test_hosted_origins_refuse_remote_private_api_and_unsafe_public_urls(public, private):
    with pytest.raises(ValueError):
        AlertDeskSettings(alert_desk_public_origin=public, alert_desk_private_origin=private)


def test_hosted_https_gateway_host_origin_cookie_and_private_destination(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    origin = "https://connect-test.example.test"
    private = "http://127.0.0.1:8017"
    calls = []

    def backend(request):
        calls.append(request)
        if request.url.path == "/access/challenge":
            return httpx.Response(200, json={"token": "s" * 43})
        return httpx.Response(200, json={"cases": [], "count": 0})

    app = create_app("test-secret-" * 4, public_origin=origin, private_origin=private,
                     transport=httpx.MockTransport(backend))
    with TestClient(app, base_url=origin, client=("127.0.0.1", 1234)) as client:
        assert "TEST · Synthetic data only" in client.get("/alerts/access").text
        assert client.get("/alerts", headers={"Host": "attacker.test"}).status_code == 403
        path = "/alerts/access/challenge"
        result = client.post(path, headers={"Origin": origin}, json={"token": "t" * 43})
        # Invitation starts a mailbox challenge, not a verified participant session.
        assert result.status_code == 200
        assert "Secure" in result.headers["set-cookie"]
        assert "HttpOnly" in result.headers["set-cookie"]
        assert str(calls[-1].url).startswith(private + "/")
        assert calls[-1].headers["authorization"].startswith("Bearer ")
        assert client.post(path, headers={"Origin": "https://attacker.test"}, json={"token": "t" * 43}).status_code == 403
        client.cookies.set(ACCESS_COOKIE, "s" * 43, path="/alerts")
        for _ in range(118):
            assert client.post(path, headers={"Origin": origin}, json={"token": "t" * 43}).status_code == 200
        limited = client.post(path, headers={"Origin": origin}, json={"token": "t" * 43})
        assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
        assert client.get("/alerts/access").status_code == 200
    with TestClient(app, base_url=origin, client=("192.0.2.1", 1234)) as outsider:
        assert outsider.get("/alerts", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403
    with TestClient(app, base_url=origin.replace("https:", "http:"), client=("127.0.0.1", 1234)) as proxy:
        redirect = proxy.get("/alerts/access/", follow_redirects=False, headers={"X-Forwarded-Proto": "http"})
        assert redirect.status_code == 307
        assert redirect.headers["location"] == origin + "/alerts/access"


def test_all_mail_links_use_hosted_origin_without_external_delivery(monkeypatch):
    from app.domain.investigations import pilot_mail

    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ALERT_DESK_TEST_ENABLED", "true")
    monkeypatch.setenv("ALERT_DESK_PUBLIC_ORIGIN", "https://connect-test.example.test")
    messages = []
    monkeypatch.setattr(pilot_mail, "deliver", lambda *args: messages.append(args))
    pilot_mail.send_access("end_user@example.test", "t" * 43)
    pilot_mail.send_case_update("end_user@example.test", "DEMO-A3-1", 1)
    pilot_mail.send_response_request("end_user@example.test", "DEMO-A3-1", 1, "2026-11-30")
    pilot_mail.send_response_reminder("end_user@example.test", [("DEMO-A3-1", "end_user", "2026-11-30", 1)])
    assert len(messages) == 4
    assert all("https://connect-test.example.test/alerts" in m[2] and "localhost" not in m[2] for m in messages)
