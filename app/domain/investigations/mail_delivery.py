"""Durable SendGrid attempts; no message bodies, codes or capability URLs stored."""

import hmac
import os
import re
from uuid import uuid4

import httpx

from app.alert_desk.settings import mail_origin
from app.core.db.session import SessionFactory
from app.core.http.sensitive import sensitive_http_request
from app.domain.models import AlertDeskMailDelivery
from app.integration.artifacts.storage import utcnow


def send(settings, recipient, subject, body):
    settings.validate_delivery(recipient)
    secret = os.environ.get("ALERT_DESK_PILOT_SECRET", "")
    if len(secret) < 32:
        raise ValueError("TEST mail accountability is not configured.")
    identifier = uuid4().hex
    fingerprint = hmac.digest(secret.encode(), (subject + "\0" + body).encode(), "sha256").hex()
    kind = subject.removeprefix("SMVS Alert Desk | ")[:80]
    origin = mail_origin()
    pattern = re.escape(origin) + r"/alerts(?:/access#[A-Za-z0-9_-]{43}|/[0-9]+)(?![A-Za-z0-9_/#-])"
    links = [{"url": url, "label": "Open Alert Desk" if "/access#" in url else "Open case"}
             for url in dict.fromkeys(re.findall(pattern, body))]
    # Retain legacy message for existing templates; the revised template renders
    # message_text plus one explicit link, avoiding an auto-linked duplicate URL.
    message_text = body
    for link in links:
        message_text = message_text.replace(link["url"], "")
    message_text = "\n".join(
        line.rstrip() for line in message_text.splitlines()
        if line.strip() not in {"Open:", "Open your organisation’s Alert Desk:",
            "Open your case:", "Open the case to review the current instructions:"}
    ).strip()
    payload = {
        "from": {"email": settings.alert_desk_mail_from, "name": "SMVS Alert Desk TEST"},
        "template_id": settings.alert_desk_sendgrid_template_id,
        "custom_args": {"smvs_test_delivery": identifier},
        "personalizations": [{"to": [{"email": recipient}], "dynamic_template_data": {
            "subject": "[TEST] " + subject, "message": body, "links": links,
            "environment": "TEST", "heading": kind, "message_text": message_text,
            "brand_logo_url": origin + "/alerts/brand/smvs-alert-desk-wide.png",
        }}],
        "tracking_settings": {"click_tracking": {"enable": False, "enable_text": False}, "open_tracking": {"enable": False}},
    }
    # Refuse network I/O unless an attempt is durably retained first.
    try:
        with SessionFactory() as s, s.begin():
            s.add(AlertDeskMailDelivery(id=identifier, recipient=recipient, kind=kind,
                                      template_id=settings.alert_desk_sendgrid_template_id,
                                      fingerprint=fingerprint, attempted_at=utcnow(), status="sending"))
    except Exception:  # noqa: BLE001 - deny send/confirmation on any audit-store failure
        raise ValueError("Email was not sent: delivery recording is unavailable.") from None
    status, http_status, provider_id = "uncertain", None, None
    try:
        with sensitive_http_request(), httpx.Client(timeout=15, trust_env=False, follow_redirects=False) as client:
            response = client.post("https://api.sendgrid.com/v3/mail/send", json=payload,
                                   headers={"Authorization": "Bearer " + settings.alert_desk_sendgrid_api_key.get_secret_value()})
        http_status = response.status_code
        status = "accepted" if http_status == 202 else "failed" if 400 <= http_status < 500 else "uncertain"
        value = response.headers.get("x-message-id", "")
        provider_id = value if re.fullmatch(r"[A-Za-z0-9._-]{1,200}", value) else None
    except httpx.HTTPError:
        pass
    try:
        with SessionFactory() as s, s.begin():
            row = s.get(AlertDeskMailDelivery, identifier, with_for_update=True)
            row.status, row.http_status, row.provider_id, row.finished_at = status, http_status, provider_id, utcnow()
    except Exception:  # noqa: BLE001 - deny send/confirmation on any audit-store failure
        raise ValueError("Email outcome is unconfirmed. Review delivery history before retrying.") from None
    if status != "accepted":
        raise ValueError("Email delivery was not confirmed. Review delivery history before retrying.")
