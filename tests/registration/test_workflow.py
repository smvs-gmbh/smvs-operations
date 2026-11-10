import base64
import hashlib
import hmac
import json
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.db.session import get_session
from app.domain.crm import registrations as internal
from app.domain.models import (
    CRMContact,
    CRMEndUser,
    EndUserRegistration,
    RegistrationEvent,
)
from app.portal import registration_routes
from app.registration import service
from app.registration.crypto import decrypt
from app.registration.gateway import create_app
from app.registration.mail import send_pending
from app.registration.models import IntakeBase, IntakeRegistration
from app.registration.schema import FIELDS
from app.registration.settings import IntakeSettings

ANSWER = "  synthetic-secret-answer-Ω  "


def submission():
    values = {k: "Example" for k in FIELDS}
    values.update(
        name="Synthetic Pharmacy",
        gln="7601001301252",
        email="spoc@example.test",
        first_name="Test",
        last_name="Person",
        terms_accepted=True,
        security_answer=ANSWER,
    )
    return {
        "eventId": "event-001",
        "eventType": "FORM_RESPONSE",
        "data": {
            "formId": "w7AWGA",
            "submissionId": "submission-001",
            "createdAt": service.now().isoformat() + "Z",
            "fields": [
                {"key": "question_" + FIELDS[k], "value": v} for k, v in values.items()
            ],
        },
    }


@pytest.fixture
def intake(tmp_path):
    settings = IntakeSettings(
        _env_file=None,
        registration_database_url="sqlite:///" + str(tmp_path / "intake.db"),
        registration_encryption_key=Fernet.generate_key().decode(),
        registration_exchange_secret="x" * 40,
        tally_registration_signing_secret="s" * 40,
        registration_mail_from="registration@example.test",
        registration_mail_link_field="confirmation_url",
        sendgrid_api_key="synthetic-key",
    )
    engine = create_engine(
        settings.registration_database_url.get_secret_value(),
        connect_args={"check_same_thread": False},
    )
    IntakeBase.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with TestClient(
        create_app(settings, factory), base_url="http://localhost:8013"
    ) as client:
        yield client, factory, settings
    engine.dispose()


def post(client, settings, payload=None):
    raw = json.dumps(
        payload or submission(), ensure_ascii=False, separators=(",", ":")
    ).encode()
    sig = base64.b64encode(
        hmac.new(
            settings.tally_registration_signing_secret.get_secret_value().encode(),
            raw,
            hashlib.sha256,
        ).digest()
    ).decode()
    return client.post(
        "/webhooks/tally/registrations",
        content=raw,
        headers={"content-type": "application/json", "tally-signature": sig},
    )


def token(factory, settings):
    with factory() as s:
        r = s.scalar(select(IntakeRegistration))
        return decrypt(
            settings.registration_encryption_key.get_secret_value(), r.token_ciphertext
        )["token"]


def exchange(client, settings):
    r = client.get(
        "/exchange/registrations",
        headers={
            "Authorization": "Bearer "
            + settings.registration_exchange_secret.get_secret_value()
        },
    )
    assert r.status_code == 200
    return r.json()["registrations"]


def test_signed_idempotent_encrypted_intake_with_no_core_routes(intake):
    client, factory, settings = intake
    assert (
        client.post("/webhooks/tally/registrations", json=submission()).status_code
        == 401
    )
    assert post(client, settings).status_code == 200
    assert post(client, settings).status_code == 200
    other = submission()
    other["eventId"] = "retry-new-event-id"
    assert post(client, settings, other).status_code == 200
    with factory() as s:
        rows = s.scalars(select(IntakeRegistration)).all()
        assert len(rows) == 1
        assert (
            ANSWER not in rows[0].payload_ciphertext
            and "spoc@example.test" not in rows[0].payload_ciphertext
        )
        assert rows[0].token_digest != token(factory, settings)
    assert client.get("/exchange/registrations").status_code == 401
    for path in (
        "/crm/end-users",
        "/products",
        "/exceptions",
        "/workflows",
        "/admin/users",
        "/docs",
    ):
        assert client.get(path).status_code == 404
    wrong = submission()
    wrong["data"]["formId"] = "different"
    assert post(client, settings, wrong).status_code == 422
    assert client.get("/confirm").headers["referrer-policy"] == "no-referrer"


def test_explicit_email_confirmation_origin_expiry_and_replay(intake):
    client, factory, settings = intake
    post(client, settings)
    raw = token(factory, settings)
    assert client.get("/confirm", params={"token": raw}).status_code == 200
    with factory() as s:
        assert s.scalar(select(IntakeRegistration)).confirmed_at is None
    assert (
        client.post(
            "/confirm",
            json={"token": raw},
            headers={"origin": "https://foreign.example.test"},
        ).status_code
        == 403
    )
    result = client.post(
        "/confirm", json={"token": raw}, headers={"origin": "http://localhost:8013"}
    )
    assert result.status_code == 200
    assert (
        client.post(
            "/confirm", json={"token": raw}, headers={"origin": "http://localhost:8013"}
        ).status_code
        == 400
    )
    with factory() as s:
        r = s.scalar(select(IntakeRegistration))
        assert r.token_digest is None and r.token_ciphertext is None
    assert exchange(client, settings)[0]["confirmed_at"]


def test_core_state_machine_crm_contacts_and_security_lifecycle(intake, portal):
    client, intake_factory, settings = intake
    _, core = portal
    post(client, settings)
    data = exchange(client, settings)[0]
    key = settings.registration_encryption_key.get_secret_value()
    with core.begin() as s:
        r = internal.import_intake(s, data, key)
        rid = r.id
    with core.begin() as s:
        internal.import_intake(s, data, key)
    with core() as s:
        assert s.scalar(select(func.count()).select_from(CRMEndUser)) == 1
        assert s.scalar(select(func.count()).select_from(CRMContact)) == 1
        r = s.get(EndUserRegistration, rid)
        assert r.status == "awaiting_email"
        with pytest.raises(ValueError):
            internal.act(s, r, "approve", "reviewer@example.test")
        assert ANSWER not in json.dumps(s.get(CRMEndUser, r.end_user_id).profile)
        assert ANSWER not in r.security_ciphertext
    raw = token(intake_factory, settings)
    client.post(
        "/confirm", json={"token": raw}, headers={"origin": "http://localhost:8013"}
    )
    data = exchange(client, settings)[0]
    with core.begin() as s:
        r = internal.import_intake(s, data, key)
        assert r.status == "needs_review"
        internal.act(s, r, "approve", "reviewer@example.test", "Organisation checked")
    with core.begin() as s:
        r = s.get(EndUserRegistration, rid)
        assert (
            internal.security_data(s, r, key, "reviewer@example.test")[
                "security_answer"
            ]
            == ANSWER
        )
        internal.act(
            s, r, "nmvs_created", "reviewer@example.test", nmvs_id="NMVS-SYNTHETIC-001"
        )
        assert r.security_ciphertext is None
        internal.act(
            s, r, "reopen", "reviewer@example.test", note="Repeat review for testing"
        )
        assert r.status == "needs_review" and r.security_ciphertext is None
        assert r.nmvs_organisation_id == "NMVS-SYNTHETIC-001"
    with core() as s:
        actions = s.scalars(
            select(RegistrationEvent).where(
                RegistrationEvent.actor == "reviewer@example.test"
            )
        ).all()
        assert {r.action for r in actions} >= {
            "review_approved",
            "security_data_viewed",
            "nmvs_creation_recorded",
            "review_reopened",
        }
    ack = client.post(
        "/exchange/registrations/ack",
        json={"id": data["id"], "revision": data["revision"]},
        headers={
            "Authorization": "Bearer "
            + settings.registration_exchange_secret.get_secret_value()
        },
    )
    assert ack.status_code == 200
    with intake_factory() as s:
        assert s.scalar(select(IntakeRegistration)).payload_ciphertext is None


def test_changed_email_duplicates_and_expiry_require_review(intake, portal):
    client, _, settings = intake
    _, core = portal
    post(client, settings)
    data = exchange(client, settings)[0]
    data["confirmed_at"] = service.now().isoformat() + "Z"
    key = settings.registration_encryption_key.get_secret_value()
    with core.begin() as s:
        r = internal.import_intake(s, data, key)
        c = s.get(CRMContact, r.contact_id)
        c.profile = c.profile | {"email": "changed@example.test"}
        with pytest.raises(ValueError, match="differs"):
            internal.act(s, r, "approve", "reviewer@example.test")
        c.profile = c.profile | {"email": r.submitted_email}
        s.add(CRMEndUser(name="Existing", profile={"gln": "7601001301252"}))
        s.flush()
        with pytest.raises(ValueError, match="duplicate"):
            internal.act(s, r, "approve", "reviewer@example.test")
        internal.act(s, r, "approve", "reviewer@example.test", duplicates_checked=True)
        r.security_expires_at = service.now() - timedelta(seconds=1)
        with pytest.raises(ValueError, match="expired"):
            internal.security_data(s, r, key, "reviewer@example.test")
        internal.purge_expired(s)
        assert r.security_ciphertext is None


def test_sendgrid_uses_existing_template_and_never_retries_uncertain_delivery(
    intake, monkeypatch
):
    client, factory, settings = intake
    post(client, settings)
    calls = []

    def send(self, url, **kwargs):
        calls.append(kwargs["json"])
        raise httpx.ReadTimeout("synthetic timeout")

    monkeypatch.setattr(httpx.Client, "post", send)
    assert send_pending(factory, settings) == 0
    assert send_pending(factory, settings) == 0
    assert len(calls) == 1
    payload = calls[0]
    assert payload["template_id"] == "d-3cae560da6c644aa92b54d4e170b059b"
    assert (
        "/confirm#"
        in payload["personalizations"][0]["dynamic_template_data"]["confirmation_url"]
    )
    assert ANSWER not in json.dumps(payload)
    assert payload["tracking_settings"]["click_tracking"]["enable"] is False
    with factory() as s:
        assert s.scalar(select(IntakeRegistration)).mail_status == "uncertain"


def test_internal_ui_approval_version_guard_and_secret_not_in_get(
    intake, portal, monkeypatch
):
    client, _, settings = intake
    web, core = portal
    post(client, settings)
    data = exchange(client, settings)[0]
    data["confirmed_at"] = service.now().isoformat() + "Z"
    key = settings.registration_encryption_key.get_secret_value()
    with core.begin() as s:
        r = internal.import_intake(s, data, key)
        rid = r.id
        version = r.version
    web.app.include_router(registration_routes.router)

    def identity(request: Request):
        request.state.portal_user = SimpleNamespace(
            id=1, email="reviewer@example.test", is_nmvo=True
        )
        with core() as session:
            yield session

    web.app.dependency_overrides[get_session] = identity

    monkeypatch.setattr(
        registration_routes,
        "get_settings",
        lambda: SimpleNamespace(
            registration_intake_url=None, registration_encryption_key=SecretStr(key)
        ),
    )
    page = web.get("/workflows/registrations")
    assert page.status_code == 200 and "Needs review" in page.text
    filtered = web.get(
        "/workflows/registrations",
        params={
            "tv_registrations_rules": json.dumps(
                [{"field": "c2", "operator": "equals", "value": "Needs review"}]
            )
        },
    )
    assert filtered.status_code == 200 and "1 results" in filtered.text
    empty = web.get(
        "/workflows/registrations",
        params={
            "tv_registrations_rules": json.dumps(
                [{"field": "c2", "operator": "equals", "value": "Rejected"}]
            )
        },
    )
    assert (
        empty.status_code == 200 and "No registrations in this selection" in empty.text
    )
    detail = web.get(f"/workflows/registrations/{rid}")
    assert detail.status_code == 200 and ANSWER not in detail.text
    path = f"/workflows/registrations/{rid}"
    assert (
        web.post(
            path,
            data={"command": "approve", "version": str(version)},
            headers={"origin": "http://testserver"},
        ).status_code
        == 200
    )
    stale = web.post(
        path,
        data={"command": "reject", "version": str(version), "note": "Testing"},
        headers={"origin": "http://testserver"},
    )
    assert stale.status_code == 409
    with core() as s:
        current = s.get(EndUserRegistration, rid).version
    revealed = web.post(
        path + "/security",
        data={"version": str(current)},
        headers={"origin": "http://testserver"},
    )
    assert revealed.status_code == 200 and ANSWER in revealed.text


def test_expired_confirmation_can_be_replaced_but_previous_link_is_invalid(intake):
    client, factory, settings = intake
    post(client, settings)
    old = token(factory, settings)
    with factory.begin() as s:
        r = s.scalar(select(IntakeRegistration))
        r.token_expires_at = service.now() - timedelta(seconds=1)
    assert (
        client.post(
            "/confirm", json={"token": old}, headers={"origin": "http://localhost:8013"}
        ).status_code
        == 400
    )
    data = exchange(client, settings)[0]
    headers = {
        "Authorization": "Bearer "
        + settings.registration_exchange_secret.get_secret_value()
    }
    result = client.post(
        "/exchange/registrations/resend",
        json={"id": data["id"], "revision": data["revision"]},
        headers=headers,
    )
    assert result.status_code == 200
    new = token(factory, settings)
    assert new != old
    assert (
        client.post(
            "/confirm", json={"token": old}, headers={"origin": "http://localhost:8013"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/confirm", json={"token": new}, headers={"origin": "http://localhost:8013"}
        ).status_code
        == 200
    )


def test_pull_commits_crm_before_ack_and_retries_do_not_duplicate(
    intake, portal, monkeypatch
):
    from app.domain.crm import registration_sync as sync

    client, _, settings = intake
    _, core = portal
    post(client, settings)
    real_client = httpx.Client
    failure = [True]

    def handle(request):
        if request.method == "GET":
            response = client.get(
                request.url.path,
                headers={"Authorization": request.headers["Authorization"]},
            )
        else:
            with core() as s:
                assert (
                    s.scalar(select(func.count()).select_from(EndUserRegistration)) == 1
                )
            if failure[0]:
                failure[0] = False
                return httpx.Response(503)
            response = client.post(
                request.url.path,
                content=request.content,
                headers={
                    "Authorization": request.headers["Authorization"],
                    "Content-Type": "application/json",
                },
            )
        return httpx.Response(response.status_code, content=response.content)

    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(
        sync.httpx, "Client", lambda **kw: real_client(transport=transport, **kw)
    )
    config = SimpleNamespace(
        registration_intake_url="http://localhost:8013",
        environment="development",
        registration_exchange_secret=settings.registration_exchange_secret,
        registration_encryption_key=settings.registration_encryption_key,
    )
    with pytest.raises(httpx.HTTPStatusError):
        sync.pull(core, config)
    assert sync.pull(core, config) == 1
    with core() as s:
        assert s.scalar(select(func.count()).select_from(CRMEndUser)) == 1
        assert s.scalar(select(func.count()).select_from(CRMContact)) == 1


def test_temporary_expiry_erases_public_payload_and_pending_contacts_cannot_be_assigned(
    intake, portal
):
    from fastapi import HTTPException

    from app.portal.crm_routes import contact_assignments

    client, factory, settings = intake
    _, core = portal
    post(client, settings)
    data = exchange(client, settings)[0]
    with core.begin() as s:
        r = internal.import_intake(
            s, data, settings.registration_encryption_key.get_secret_value()
        )
        with pytest.raises(HTTPException):
            contact_assignments({"spoc_ids": str(r.contact_id)}, s, {})
    with factory.begin() as s:
        r = s.scalar(select(IntakeRegistration))
        r.expires_at = service.now() - timedelta(seconds=1)
        service.purge(s)
        assert r.payload_ciphertext is None and r.token_digest is None
    with core.begin() as s:
        # An unseen, already purged source yields a visible exception to review, not a fake CRM identity.
        expired = dict(
            data, id="8f36c953-cece-4c56-a23c-e5bd44dd6a90", values=None, revision=2
        )
        r = internal.import_intake(
            s, expired, settings.registration_encryption_key.get_secret_value()
        )
        assert r.status == "expired" and r.end_user_id is None


def test_intake_database_cannot_use_core_or_production_sqlite(intake, tmp_path):
    from app.registration.store import factory

    _, _, settings = intake
    with pytest.raises(ValueError):
        factory(settings.model_copy(update={"registration_environment": "production"}))
    with pytest.raises(ValueError):
        factory(
            settings.model_copy(
                update={
                    "registration_database_url": SecretStr(
                        "mysql+pymysql://example:example@localhost/smvs_operations"
                    )
                }
            )
        )


def test_unreviewed_registration_cannot_be_approved_without_nmvo_identity(
    intake, portal
):
    client, _, settings = intake
    web, core = portal
    post(client, settings)
    data = exchange(client, settings)[0]
    with core.begin() as s:
        r = internal.import_intake(
            s, data, settings.registration_encryption_key.get_secret_value()
        )
        identifier = r.id
    web.app.include_router(registration_routes.router)
    assert (
        web.post(
            f"/workflows/registrations/{identifier}",
            data={"command": "approve", "version": "1"},
            headers={"origin": "http://testserver"},
        ).status_code
        == 403
    )
