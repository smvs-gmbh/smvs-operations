"""Stateless public relay and atomic private CRM registration acceptance."""

import base64
import hashlib
import hmac
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.connect.gateway import create_app
from app.connect.settings import ConnectSettings
from app.domain.models import (
    CRMContact,
    CRMEndUser,
    EndUserRegistration,
    RegistrationEvent,
    RegistrationReceipt,
)
from app.registration import internal_service
from app.registration.crypto import decrypt
from app.registration.internal_gateway import create_app as private_app
from app.registration.internal_settings import InternalRegistrationSettings
from app.registration.internal_worker import process
from app.registration.schema import FIELDS, parse_submission
from app.registration.service import now


@pytest.fixture
def direct(portal):
    _, factory = portal
    internal = InternalRegistrationSettings(
        _env_file=None,
        connect_api_secret="a" * 48,
        tally_registration_signing_secret="b" * 48,
        registration_encryption_key=Fernet.generate_key().decode(),
        sendgrid_api_key="synthetic-mail-key",
    )
    public = ConnectSettings(
        _env_file=None,
        internal_origin="https://registration.internal.test",
        api_secret=internal.connect_api_secret,
        tally_signing_secret=internal.tally_registration_signing_secret,
    )
    backend = private_app(internal, factory)
    gateway = create_app(public, transport=httpx.ASGITransport(app=backend))
    with TestClient(gateway, base_url=public.public_origin) as client:
        yield SimpleNamespace(
            client=client,
            factory=factory,
            internal=internal,
            public=public,
            backend=backend,
        )


def request_data(direct):
    values = {k: "Synthetic direct registration" for k in FIELDS}
    values.update(
        name="Connect Test Pharmacy",
        gln="0000000000000",
        first_name="Fixture",
        last_name="Person",
        email="spoc@example.test",
        terms_accepted=True,
        security_answer="synthetic-private-answer",
    )
    payload = {
        "eventId": "direct-event",
        "eventType": "FORM_RESPONSE",
        "data": {
            "formId": "w7AWGA",
            "submissionId": "direct-submission",
            "createdAt": now().isoformat() + "Z",
            "fields": [
                {"key": "question_" + FIELDS[k], "value": v} for k, v in values.items()
            ],
        },
    }
    raw = json.dumps(payload, ensure_ascii=False).encode()
    signature = base64.b64encode(
        hmac.new(
            direct.internal.tally_registration_signing_secret.get_secret_value().encode(),
            raw,
            hashlib.sha256,
        ).digest()
    ).decode()
    return raw, {"Content-Type": "application/json", "Tally-Signature": signature}


def submit(direct):
    raw, headers = request_data(direct)
    return direct.client.post(
        "/webhooks/tally/registrations", content=raw, headers=headers
    )


def test_rejected_webhook_diagnostics_never_log_form_answers(direct, caplog):
    raw, _ = request_data(direct)
    payload = json.loads(raw)
    for field in payload["data"]["fields"]:
        if field["key"] == "question_" + FIELDS["gln"]:
            field["value"] = "invalid"
        if field["key"] == "question_" + FIELDS["email"]:
            field["value"] = "private-test@example.test"
        if field["key"] == "question_" + FIELDS["security_answer"]:
            field["value"] = "PRIVATE-ANSWER-MUST-NOT-BE-LOGGED"
    raw = json.dumps(payload).encode()
    signature = base64.b64encode(
        hmac.new(
            direct.internal.tally_registration_signing_secret.get_secret_value().encode(),
            raw,
            hashlib.sha256,
        ).digest()
    ).decode()
    response = direct.client.post(
        "/webhooks/tally/registrations",
        content=raw,
        headers={"Content-Type": "application/json", "Tally-Signature": signature},
    )
    assert response.status_code == 422
    assert "format rejected" in caplog.text
    assert "private-test@example.test" not in caplog.text
    assert "PRIVATE-ANSWER-MUST-NOT-BE-LOGGED" not in caplog.text
    assert "Synthetic direct registration" not in caplog.text


def test_observed_tally_field_keys_and_selection_shape(direct):
    # Independent fixture: actual webhook keys, not generated from implementation FIELDS.
    payload = json.loads(
        (Path(__file__).parent / "fixtures/tally-registration.json").read_text()
    )
    raw = json.dumps(payload).encode()
    signature = base64.b64encode(
        hmac.new(
            direct.internal.tally_registration_signing_secret.get_secret_value().encode(),
            raw,
            hashlib.sha256,
        ).digest()
    ).decode()
    for _ in range(2):
        assert (
            direct.client.post(
                "/webhooks/tally/registrations",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    "Tally-Signature": signature,
                },
            ).status_code
            == 200
        )
    with direct.factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(RegistrationReceipt)) == 1
        )
        receipt = session.scalar(select(RegistrationReceipt))
        values = decrypt(
            direct.internal.registration_encryption_key.get_secret_value(),
            receipt.payload_ciphertext,
        )
        assert values["organisation_type"] == "Apotheke"
        assert values["country"] == "Schweiz"
        assert values["terms_accepted"] is True
        assert values["security_answer"] == "  Synthetic answer Ω  "
    for field in payload["data"]["fields"]:
        if field["key"] == "question_O75bzk":
            field["value"] = "123"
    with pytest.raises(ValueError, match="13-digit GLN"):
        parse_submission(payload)


def token(direct):
    with direct.factory() as s:
        receipt = s.scalar(select(RegistrationReceipt))
        return decrypt(
            direct.internal.registration_encryption_key.get_secret_value(),
            receipt.token_ciphertext,
        )["token"]


def confirm(direct, value):
    return direct.client.post(
        "/confirm",
        json={"token": value},
        headers={"Origin": direct.public.public_origin},
    )


def test_direct_commit_crm_confirmation_and_repeat_safe_delivery(direct):
    assert direct.client.get("/").status_code == 200
    assert "SMVS Connect" in direct.client.get("/").text
    assert submit(direct).json() == {"received": True}
    assert submit(direct).status_code == 200
    with direct.factory() as s:
        for model in (RegistrationReceipt, EndUserRegistration, CRMEndUser, CRMContact):
            assert s.scalar(select(func.count()).select_from(model)) == 1
        receipt = s.scalar(select(RegistrationReceipt))
        assert "synthetic-private-answer" not in receipt.payload_ciphertext
        row = s.scalar(select(EndUserRegistration))
        assert row.status == "awaiting_email"
        assert "security_answer" not in s.scalar(select(CRMEndUser)).profile
    value = token(direct)
    assert direct.client.get("/confirm").status_code == 200
    with direct.factory() as s:
        assert s.scalar(select(EndUserRegistration)).confirmed_at is None
    assert (
        direct.client.post(
            "/confirm", json={"token": value}, headers={"Origin": "https://other.test"}
        ).status_code
        == 403
    )
    assert confirm(direct, value).json() == {"confirmed": True}
    assert confirm(direct, value).status_code == 400
    with direct.factory() as s:
        row = s.scalar(select(EndUserRegistration))
        receipt = s.scalar(select(RegistrationReceipt))
        assert row.status == "needs_review" and row.confirmed_at
        assert receipt.payload_ciphertext is None
        assert receipt.token_digest is None and receipt.token_ciphertext is None
        assert list(s.scalars(select(RegistrationEvent.action))) == [
            "received",
            "email_confirmed",
        ]
    assert submit(direct).status_code == 200
    with direct.factory() as s:
        assert s.scalar(select(func.count()).select_from(CRMEndUser)) == 1


def test_public_and_private_capabilities_are_narrow(direct):
    for path in [
        "/crm",
        "/exceptions",
        "/exchange/registrations",
        "/docs",
        "/v1/registrations/submissions",
    ]:
        assert direct.client.get(path).status_code == 404
    assert (
        direct.client.get("/confirm", headers={"Host": "other.test"}).status_code == 403
    )
    raw, headers = request_data(direct)
    assert (
        direct.client.post(
            "/webhooks/tally/registrations",
            content=raw,
            headers={"content-type": "application/json"},
        ).status_code
        == 401
    )
    with TestClient(
        direct.backend,
        base_url=direct.public.internal_origin,
        client=("127.0.0.1", 12345),
    ) as backend:
        assert (
            backend.post(
                "/v1/registrations/submissions", content=raw, headers=headers
            ).status_code
            == 401
        )
        auth = {
            "Authorization": "Bearer "
            + direct.internal.connect_api_secret.get_secret_value()
        }
        assert backend.get("/crm", headers=auth).status_code == 404
        assert (
            backend.get("/v1/registrations/submissions", headers=auth).status_code
            == 405
        )
        assert (
            backend.post(
                "/v1/registrations/submissions",
                content=raw,
                headers=auth | {"content-type": "application/json"},
            ).status_code
            == 401
        )
    with direct.factory() as s:
        assert s.scalar(select(func.count()).select_from(RegistrationReceipt)) == 0


@pytest.mark.parametrize(
    "status,body",
    [
        (503, b"internal-secret"),
        (401, b"secret"),
        (302, b""),
        (200, b"not-json"),
        (200, b"[]"),
        (200, b"x" * 5000),
        (200, b'{"received":true,"private":"data"}'),
    ],
)
def test_failed_or_unexpected_internal_response_never_acknowledges(
    direct, status, body
):
    calls = []

    async def unavailable(request):
        calls.append(str(request.url))
        return httpx.Response(
            status, content=body, headers={"Location": "https://untrusted.test"}
        )

    public = create_app(direct.public, transport=httpx.MockTransport(unavailable))
    with TestClient(public, base_url=direct.public.public_origin) as client:
        raw, headers = request_data(direct)
        response = client.post(
            "/webhooks/tally/registrations", content=raw, headers=headers
        )
        assert response.status_code == 503
        assert response.json() == {
            "detail": "Registration processing is temporarily unavailable. Please try again."
        }
    assert calls == [direct.public.internal_origin + "/v1/registrations/submissions"]


def test_database_failure_rolls_back_receipt_crm_and_outbox(direct, monkeypatch):
    original = internal_service.receive

    def fail_after_write(session, payload, settings):
        original(session, payload, settings)
        raise SQLAlchemyError("synthetic-private-failure")

    monkeypatch.setattr(internal_service, "receive", fail_after_write)
    assert submit(direct).status_code == 503
    with direct.factory() as s:
        for model in (
            RegistrationReceipt,
            EndUserRegistration,
            CRMEndUser,
            CRMContact,
            RegistrationEvent,
        ):
            assert s.scalar(select(func.count()).select_from(model)) == 0
    monkeypatch.setattr(internal_service, "receive", original)
    assert submit(direct).status_code == 200


def test_response_loss_after_commit_can_be_retried_without_duplicates(direct):
    backend = httpx.ASGITransport(app=direct.backend)
    first = True

    class ResponseLoss(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            nonlocal first
            response = await backend.handle_async_request(request)
            if first:
                first = False
                raise httpx.ReadTimeout("synthetic response loss", request=request)
            return response

    with TestClient(
        create_app(direct.public, transport=ResponseLoss()),
        base_url=direct.public.public_origin,
    ) as client:
        raw, headers = request_data(direct)
        assert (
            client.post(
                "/webhooks/tally/registrations", content=raw, headers=headers
            ).status_code
            == 503
        )
        assert (
            client.post(
                "/webhooks/tally/registrations", content=raw, headers=headers
            ).status_code
            == 200
        )
    with direct.factory() as s:
        for model in (RegistrationReceipt, CRMEndUser, CRMContact):
            assert s.scalar(select(func.count()).select_from(model)) == 1


def test_internal_mail_and_resend_update_workflow_without_pull(direct, monkeypatch):
    assert submit(direct).status_code == 200
    original = token(direct)
    mock = MagicMock()
    mock.__enter__.return_value.post.return_value.status_code = 202
    monkeypatch.setattr("app.registration.mail.httpx.Client", lambda **kwargs: mock)
    assert process(direct.factory, direct.internal) == 1
    assert process(direct.factory, direct.internal) == 0
    send = mock.__enter__.return_value.post
    assert send.call_count == 1
    payload = send.call_args.kwargs["json"]
    dynamic = payload["personalizations"][0]["dynamic_template_data"]
    assert (
        dynamic["confirmation_link"]
        == direct.public.public_origin + "/confirm#" + original
    )
    assert payload["from"]["email"] == "office@smvs-gmbh.ch"
    assert "security_answer" not in dynamic
    with direct.factory.begin() as s:
        row = s.scalar(select(EndUserRegistration))
        assert row.confirmation_mail_status == "accepted"
        receipt = s.scalar(select(RegistrationReceipt))
        receipt.mail_attempted_at = now() - timedelta(minutes=6)
        internal_service.resend(
            s,
            row,
            "Synthetic reviewer",
            direct.internal.registration_encryption_key.get_secret_value(),
        )
        assert row.confirmation_mail_status == "queued"
    assert token(direct) != original
    assert confirm(direct, original).status_code == 400
    assert confirm(direct, token(direct)).status_code == 200


def test_targeted_mail_run_does_not_send_other_queued_registrations(
    direct, monkeypatch
):
    assert submit(direct).status_code == 200
    with direct.factory() as session:
        selected_id = session.scalar(select(RegistrationReceipt.id))
    raw, _ = request_data(direct)
    other = json.loads(raw)
    other["eventId"] = "other-event"
    other["data"]["submissionId"] = "other-submission"
    raw = json.dumps(other).encode()
    signature = base64.b64encode(
        hmac.new(
            direct.internal.tally_registration_signing_secret.get_secret_value().encode(),
            raw,
            hashlib.sha256,
        ).digest()
    ).decode()
    assert (
        direct.client.post(
            "/webhooks/tally/registrations",
            content=raw,
            headers={"Content-Type": "application/json", "Tally-Signature": signature},
        ).status_code
        == 200
    )
    mock = MagicMock()
    mock.__enter__.return_value.post.return_value.status_code = 202
    monkeypatch.setattr("app.registration.mail.httpx.Client", lambda **kwargs: mock)
    assert process(direct.factory, direct.internal, receipt_id="nonexistent") == 0
    assert process(direct.factory, direct.internal, receipt_id=selected_id) == 1
    assert process(direct.factory, direct.internal, receipt_id=selected_id) == 0
    assert mock.__enter__.return_value.post.call_count == 1
    with direct.factory() as session:
        statuses = dict(
            session.execute(
                select(
                    RegistrationReceipt.id,
                    RegistrationReceipt.mail_status,
                )
            ).all()
        )
        assert statuses[selected_id] == "accepted"
        assert list(statuses.values()).count("queued") == 1


def test_internal_expiry_erases_both_receipt_and_security_answer(direct):
    assert submit(direct).status_code == 200
    with direct.factory.begin() as s:
        s.scalar(select(RegistrationReceipt)).expires_at = now() - timedelta(seconds=1)
        s.scalar(select(EndUserRegistration)).security_expires_at = now() - timedelta(
            seconds=1
        )
    assert process(direct.factory, direct.internal, mail=False) == 0
    with direct.factory() as s:
        row = s.scalar(select(EndUserRegistration))
        receipt = s.scalar(select(RegistrationReceipt))
        assert row.security_ciphertext is None
        assert receipt.payload_ciphertext is None and receipt.token_ciphertext is None
        assert row.confirmation_mail_status == "expired"


def test_public_settings_require_tls_and_have_no_storage_or_mail_credentials(direct):
    fields = ConnectSettings.model_fields
    assert not any(
        "database" in key or "sendgrid" in key or "encryption" in key for key in fields
    )
    with pytest.raises(ValueError):
        ConnectSettings(
            _env_file=None,
            internal_origin="http://10.100.32.195",
            api_secret="a" * 48,
            tally_signing_secret="b" * 48,
        )
    with pytest.raises(ValueError):
        ConnectSettings(
            _env_file=None,
            internal_origin="https://registration.internal.test/other-path",
            api_secret="a" * 48,
            tally_signing_secret="b" * 48,
        )


def test_public_distribution_imports_without_any_core_or_database_modules(tmp_path):
    import hashlib
    import subprocess
    import sys
    import zipfile

    from scripts.package_connect import package

    target = tmp_path / "connect.zip"
    package(target)
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        assert not any(
            name.startswith(("app/core/", "app/domain/"))
            or name.endswith(("models.py", "mail.py", "crypto.py"))
            for name in names
        )
        assert not any(
            name.startswith(".env") or name.endswith((".db", ".sqlite"))
            for name in names
        )
        manifest = json.loads(archive.read("MANIFEST.sha256.json"))
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        requirements = archive.read("requirements.txt").decode().lower()
        assert "sqlalchemy" not in requirements and "pymysql" not in requirements
        extracted = tmp_path / "isolated"
        archive.extractall(extracted)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            'import sys; sys.path.insert(0, sys.argv[1]); from app.connect.gateway import create_app; assert not any(m.startswith(("app.core", "app.domain", "sqlalchemy")) for m in sys.modules)',
            str(extracted),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_direct_portal_does_not_offer_pull_and_resend_is_version_checked(
    direct, portal, monkeypatch
):
    from fastapi import Request
    from pydantic import SecretStr

    from app.core.db.session import get_session
    from app.portal import registration_routes

    web, factory = portal
    assert submit(direct).status_code == 200
    web.app.include_router(registration_routes.router)

    def identity(request: Request):
        request.state.portal_user = SimpleNamespace(
            id=1, email="reviewer@example.test", is_nmvo=True
        )
        with factory() as session:
            yield session

    web.app.dependency_overrides[get_session] = identity
    monkeypatch.setattr(
        registration_routes,
        "get_settings",
        lambda: SimpleNamespace(
            registration_delivery_mode="direct",
            registration_encryption_key=direct.internal.registration_encryption_key,
            connect_api_secret=SecretStr("a" * 48),
        ),
    )
    page = web.get("/workflows/registrations")
    assert page.status_code == 200 and "SMVS Connect" in page.text
    assert 'action="/workflows/registrations/sync"' not in page.text
    with factory() as session:
        row = session.scalar(select(EndUserRegistration))
        identifier, version = row.id, row.version
    response = web.post(
        "/workflows/registrations/" + str(identifier),
        data={"version": str(version + 1), "command": "resend"},
        headers={"origin": "http://testserver"},
    )
    assert response.status_code == 409
    response = web.post(
        "/workflows/registrations/" + str(identifier),
        data={"version": str(version), "command": "resend"},
        headers={"origin": "http://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with factory() as session:
        assert "confirmation_resend_requested" in list(
            session.scalars(select(RegistrationEvent.action))
        )


def test_private_api_uses_real_peer_ip_and_rejects_forwarded_ip_spoofing(direct):
    settings = direct.internal.model_copy(
        update={"registration_api_allowed_ips": "10.100.37.97"}
    )
    backend = private_app(settings, direct.factory)
    raw, headers = request_data(direct)
    headers["Authorization"] = (
        "Bearer " + settings.connect_api_secret.get_secret_value()
    )
    with TestClient(
        backend, base_url=direct.public.internal_origin, client=("10.100.37.98", 12345)
    ) as client:
        response = client.post(
            "/v1/registrations/submissions",
            content=raw,
            headers=headers | {"X-Forwarded-For": "10.100.37.97"},
        )
        assert response.status_code == 403
    with direct.factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(RegistrationReceipt)) == 0
        )
    with TestClient(
        backend, base_url=direct.public.internal_origin, client=("10.100.37.97", 12345)
    ) as client:
        assert (
            client.post(
                "/v1/registrations/submissions", content=raw, headers=headers
            ).status_code
            == 200
        )
