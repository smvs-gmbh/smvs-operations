from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy import select

from app.alert_desk.mail_settings import MailSettings
from app.alert_desk.test_workspace import fixture_database
from app.domain.investigations import mail_delivery
from app.domain.models import AlertDeskMailDelivery


@pytest.fixture
def sender(tmp_path, monkeypatch):
    engine, factory = fixture_database(tmp_path / "mail.db")
    monkeypatch.setattr(mail_delivery, "SessionFactory", factory)
    monkeypatch.setenv("ALERT_DESK_PILOT_SECRET", "test-mail-hmac-" * 4)
    monkeypatch.setenv("ALERT_DESK_PUBLIC_ORIGIN", "https://connect-test.example.test")
    settings = MailSettings(environment="test", alert_desk_test_enabled=True,
        alert_desk_mail_mode="sendgrid", alert_desk_mail_from="alerts@example.test",
        alert_desk_sendgrid_api_key="not-a-real-key", alert_desk_sendgrid_template_id="d-" + "a" * 32,
        alert_desk_mail_recipients="end_user@example.test,mah@example.test")
    try:
        yield settings, factory
    finally:
        engine.dispose()


def transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(mail_delivery.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


@pytest.mark.parametrize("path", ["access", "login"])
def test_sendgrid_single_allowed_recipient_template_tracking_and_durable_outcome(sender, monkeypatch, path):
    settings, factory = sender
    token = "t" * 43
    body = "Open: https://connect-test.example.test/alerts/" + path + "#" + token

    def accept(request):
        import json
        with factory() as s:
            row = s.scalar(select(AlertDeskMailDelivery))
            assert row.status == "sending"
        assert str(request.url) == "https://api.sendgrid.com/v3/mail/send"
        data = json.loads(request.content)
        assert data["personalizations"][0]["to"] == [{"email": "end_user@example.test"}]
        dynamic = data["personalizations"][0]["dynamic_template_data"]
        assert dynamic["subject"].startswith("[TEST]") and dynamic["links"][0]["url"].endswith(token)
        assert body == dynamic["message"]  # Existing active templates remain usable.
        assert token not in dynamic["message_text"] and "https://" not in dynamic["message_text"]
        assert dynamic["brand_logo_url"] == "https://connect-test.example.test/alerts/brand/smvs-alert-desk-wide.png"
        assert "codex-workspace-link.invalid" not in str(dynamic)
        assert data["tracking_settings"]["click_tracking"] == {"enable": False, "enable_text": False}
        assert data["tracking_settings"]["open_tracking"] == {"enable": False}
        return httpx.Response(202, headers={"X-Message-Id": "provider-reference"})

    transport(monkeypatch, accept)
    mail_delivery.send(settings, "end_user@example.test", "SMVS Alert Desk | Invitation", body)
    with factory() as s:
        row = s.scalar(select(AlertDeskMailDelivery))
        assert row.status == "accepted" and row.http_status == 202 and row.provider_id == "provider-reference"
        assert token not in str(row.__dict__) and "not-a-real-key" not in str(row.__dict__)
        assert len(row.fingerprint) == 64


@pytest.mark.parametrize("case", ["recipient", "production", "key", "template", "sender"])
def test_unsafe_or_incomplete_mail_config_never_calls_provider(sender, monkeypatch, case):
    settings, factory = sender
    recipient = "end_user@example.test"
    if case == "recipient": recipient = "unapproved@example.test"
    if case == "production": settings.environment = "production"
    if case == "key": settings.alert_desk_sendgrid_api_key = None
    if case == "template": settings.alert_desk_sendgrid_template_id = ""
    if case == "sender": settings.alert_desk_mail_from = "bad\naddress"
    monkeypatch.setattr(mail_delivery.httpx, "Client", lambda **kw: pytest.fail("Network must be refused"))
    with pytest.raises(ValueError): mail_delivery.send(settings, recipient, "Test", "Content")
    with factory() as s: assert s.scalar(select(AlertDeskMailDelivery)) is None


@pytest.mark.parametrize("outcome,expected", [(400, "failed"), (500, "uncertain"), ("timeout", "uncertain")])
def test_delivery_failure_is_retained_without_retry(sender, monkeypatch, outcome, expected):
    settings, factory = sender
    attempts = []
    def fail(request):
        attempts.append(1)
        if outcome == "timeout": raise httpx.ReadTimeout("simulated")
        return httpx.Response(outcome)
    transport(monkeypatch, fail)
    with pytest.raises(ValueError): mail_delivery.send(settings, "end_user@example.test", "Test", "Content")
    assert len(attempts) == 1
    with factory() as s: assert s.scalar(select(AlertDeskMailDelivery)).status == expected


def test_recording_failure_prevents_send_and_outcome_failure_remains_unconfirmed(sender, monkeypatch):
    settings, factory = sender
    calls = []
    transport(monkeypatch, lambda request: calls.append(1) or httpx.Response(202))
    @contextmanager
    def unavailable():
        raise RuntimeError("No audit storage")
        yield
    monkeypatch.setattr(mail_delivery, "SessionFactory", unavailable)
    with pytest.raises(ValueError): mail_delivery.send(settings, "end_user@example.test", "Test", "Content")
    assert calls == []
    count = 0
    def lose_finish():
        nonlocal count
        count += 1
        return factory() if count == 1 else unavailable()
    monkeypatch.setattr(mail_delivery, "SessionFactory", lose_finish)
    with pytest.raises(ValueError): mail_delivery.send(settings, "end_user@example.test", "Test", "Content")
    assert calls == [1]
    with factory() as s: assert s.scalar(select(AlertDeskMailDelivery)).status == "sending"
