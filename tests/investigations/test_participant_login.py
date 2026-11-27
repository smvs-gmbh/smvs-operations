import json
import secrets
from datetime import timedelta
from hashlib import sha256

import cbor2
import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import select
from webauthn.helpers import bytes_to_base64url

from app.alert_desk.test_workspace import create_workspace, fixture_database
from app.alert_desk.web import ACCESS_COOKIE
from app.alert_desk.web import create_app as gateway
from app.domain.investigations import participant_auth as auth
from app.domain.investigations import pilot, pilot_mail
from app.domain.investigations.pilot_api import create_app
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskAuthEvent,
    AlertDeskLoginToken,
    AlertDeskParticipantPasskey,
    AlertDeskParticipantSession,
    CRMContact,
)

ORIGIN = "http://localhost:8021"
HEADERS = {"Origin": ORIGIN}
SECRET = "participant-login-test-secret-" * 2


@pytest.fixture
def login(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ALERT_DESK_PUBLIC_ORIGIN", ORIGIN)
    engine, factory = fixture_database(tmp_path / "auth.db")
    create_workspace(factory)
    messages = []
    monkeypatch.setattr(
        pilot_mail, "send_signin", lambda email, token: messages.append((email, token))
    )
    private = create_app(factory, SECRET)
    public = gateway(
        SECRET,
        public_origin=ORIGIN,
        private_origin="http://127.0.0.1:8017",
        transport=httpx.ASGITransport(app=private),
    )
    with TestClient(public, base_url=ORIGIN, client=("127.0.0.1", 1234)) as client:
        yield client, factory, messages
    engine.dispose()


def post(client, step, **body):
    return client.post("/alerts/auth/" + step, json=body, headers=HEADERS)


def magic(client, messages, email="mah@example.test"):
    assert post(client, "magic", email=email).json() == {"message": auth.NEUTRAL}
    return messages[-1][1]


def sign_in(client, messages, email="mah@example.test"):
    token = magic(client, messages, email)
    result = post(client, "consume", token=token)
    assert result.status_code == 200 and result.json()["next"] == "/alerts/account"
    return result


def registration(options, *, origin=ORIGIN):
    private = ec.generate_private_key(ec.SECP256R1())
    key = private.public_key().public_numbers()
    cid = secrets.token_bytes(32)
    cose = cbor2.dumps(
        {
            1: 2,
            3: -7,
            -1: 1,
            -2: key.x.to_bytes(32, "big"),
            -3: key.y.to_bytes(32, "big"),
        }
    )
    data = json.dumps(
        {"type": "webauthn.create", "challenge": options["challenge"], "origin": origin}
    ).encode()
    authenticator = (
        sha256(b"localhost").digest()
        + b"\x45"
        + bytes(4)
        + bytes(16)
        + len(cid).to_bytes(2, "big")
        + cid
        + cose
    )
    attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": authenticator})
    return private, {
        "id": bytes_to_base64url(cid),
        "rawId": bytes_to_base64url(cid),
        "type": "public-key",
        "response": {
            "clientDataJSON": bytes_to_base64url(data),
            "attestationObject": bytes_to_base64url(attestation),
        },
    }


def register(client):
    options = post(client, "register-options").json()
    private, credential = registration(options)
    result = post(client, "register-finish", credential=credential)
    assert result.status_code == 200, result.text
    return private, credential, options["user"]["id"]


def assertion(
    private, credential, options, handle, *, origin=ORIGIN, uv=True, counter=1
):
    data = json.dumps(
        {"type": "webauthn.get", "challenge": options["challenge"], "origin": origin}
    ).encode()
    authenticator = (
        sha256(b"localhost").digest()
        + (b"\x05" if uv else b"\x01")
        + counter.to_bytes(4, "big")
    )
    return {
        **credential,
        "response": {
            "clientDataJSON": bytes_to_base64url(data),
            "authenticatorData": bytes_to_base64url(authenticator),
            "signature": bytes_to_base64url(
                private.sign(
                    authenticator + sha256(data).digest(), ec.ECDSA(hashes.SHA256())
                )
            ),
            "userHandle": handle,
        },
    }


def test_magic_neutral_rate_limit_single_use_and_cookie(login):
    client, factory, messages = login
    assert "Sign in to Alert Desk" in client.get("/alerts").text
    assert post(client, "magic", email="unknown@example.test").json() == {
        "message": auth.NEUTRAL
    }
    assert not messages
    token = magic(client, messages, "MAH@example.test")
    assert (
        client.get("/alerts/login#" + token).status_code == 200
    )  # Viewing/scanning never consumes.
    response = post(client, "consume", token=token)
    assert response.status_code == 200 and token not in response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert (
        "MAH" in client.get("/alerts").text
        and "No investigation requested." in client.get("/alerts/6").text
    )
    assert post(client, "consume", token=token).status_code == 403
    with factory() as s:
        assert s.get(AlertDeskLoginToken, pilot.digest(token)) is None
        rows = s.scalars(select(AlertDeskParticipantSession)).all()
        assert len(rows) == 1 and rows[0].id == pilot.digest(
            client.cookies.get(ACCESS_COOKIE)
        )
        assert token not in str(rows[0].__dict__)
    for _ in range(5):
        assert post(client, "magic", email="mah@example.test").json() == {
            "message": auth.NEUTRAL
        }
    assert len(messages) == 3


def test_magic_expiry_membership_and_unconfirmed_delivery_are_neutral(
    login, monkeypatch
):
    client, factory, messages = login
    token = magic(client, messages)
    with factory.begin() as s:
        s.get(AlertDeskLoginToken, pilot.digest(token)).expires_at = (
            pilot.now() - timedelta(seconds=1)
        )
    assert post(client, "consume", token=token).status_code == 403
    token = magic(client, messages)
    with factory.begin() as s:
        grant = s.scalar(select(AlertDeskAccess).where(AlertDeskAccess.role == "mah"))
        grant.revoked_at = pilot.now()
    assert post(client, "consume", token=token).status_code == 403
    assert post(client, "magic", email="mah@example.test").json() == {
        "message": auth.NEUTRAL
    }
    assert len(messages) == 2
    monkeypatch.setattr(
        pilot_mail,
        "send_signin",
        lambda *args: (_ for _ in ()).throw(ValueError("provider unavailable")),
    )
    assert post(client, "magic", email="end_user@example.test").json() == {
        "message": auth.NEUTRAL
    }
    with factory() as s:
        assert s.scalar(
            select(AlertDeskAuthEvent).where(
                AlertDeskAuthEvent.kind == "Sign-in mail unconfirmed"
            )
        )


def test_real_passkey_registration_authentication_replay_and_logout(login):
    client, factory, messages = login
    sign_in(client, messages)
    private, credential, handle = register(client)
    assert len(client.get("/alerts/auth/account").json()["keys"]) == 1
    assert post(client, "logout").status_code == 200
    assert "Sign in to Alert Desk" in client.get("/alerts").text
    options = post(client, "options", email="mah@example.test").json()
    answer = assertion(private, credential, options, handle)
    response = post(client, "finish", credential=answer)
    assert response.status_code == 200 and response.json() == {"next": "/alerts"}
    assert "MAH" in client.get("/alerts").text
    assert post(client, "finish", credential=answer).status_code == 403
    with factory() as s:
        key = s.scalar(select(AlertDeskParticipantPasskey))
        assert key.sign_count == 1 and key.last_used_at
        assert s.scalar(
            select(AlertDeskAuthEvent).where(
                AlertDeskAuthEvent.kind == "Passkey registered"
            )
        )


@pytest.mark.parametrize(
    "failure",
    [
        "wrong_email",
        "origin",
        "uv",
        "handle",
        "revoked",
        "contact",
        "scope",
        "invitation",
        "counter",
    ],
)
def test_passkey_refuses_wrong_identity_origin_uv_revocation_and_rebinding(
    login, failure
):
    client, factory, messages = login
    sign_in(client, messages)
    private, credential, handle = register(client)
    options = post(
        client,
        "options",
        email="end_user@example.test"
        if failure == "wrong_email"
        else "mah@example.test",
    ).json()
    changes = {}
    if failure == "origin":
        changes["origin"] = "https://attacker.example.test"
    if failure == "uv":
        changes["uv"] = False
    if failure == "handle":
        handle = bytes_to_base64url(b"wrong-user")
    with factory.begin() as s:
        grant = s.scalar(select(AlertDeskAccess).where(AlertDeskAccess.role == "mah"))
        if failure == "revoked":
            s.scalar(select(AlertDeskParticipantPasskey)).revoked_at = pilot.now()
        if failure == "contact":
            s.get(CRMContact, grant.contact_id).version += 1
        if failure == "scope":
            grant.scope_key = "different"
        if failure == "invitation":
            grant.invited_at += timedelta(seconds=1)
        if failure == "counter":
            s.scalar(select(AlertDeskParticipantPasskey)).sign_count = 2
    assert (
        post(
            client,
            "finish",
            credential=assertion(private, credential, options, handle, **changes),
        ).status_code
        == 403
    )


def test_fresh_proof_required_and_revoking_key_revokes_sessions(login):
    client, factory, messages = login
    sign_in(client, messages)
    register(client)
    with factory.begin() as s:
        row = s.get(
            AlertDeskParticipantSession, pilot.digest(client.cookies.get(ACCESS_COOKIE))
        )
        row.created_at = pilot.now() - timedelta(minutes=11)
    assert post(client, "register-options").status_code == 403
    key = client.get("/alerts/auth/account").json()["keys"][0]["id"]
    assert post(client, "revoke", key=key).status_code == 403
    sign_in(client, messages)
    assert post(client, "revoke", key=key).status_code == 200
    assert "Sign in to Alert Desk" in client.get("/alerts").text
    with factory() as s:
        assert all(
            row.revoked_at for row in s.scalars(select(AlertDeskParticipantSession))
        )


def test_authentication_csrf_limits_unknown_options_and_scope_selection(login):
    client, factory, messages = login
    assert (
        client.post(
            "/alerts/auth/magic",
            json={"email": "mah@example.test"},
            headers={"Origin": "https://attacker.test"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/alerts/auth/options",
            content="x" * 66000,
            headers={**HEADERS, "Content-Type": "application/json"},
        ).status_code
        == 413
    )
    unknown = post(client, "options", email="unknown@example.test").json()
    known = post(client, "options", email="mah@example.test").json()
    assert set(unknown) == set(known) and unknown.get("allowCredentials") == known.get(
        "allowCredentials"
    )
    # A mailbox may have multiple approved roles: proof does not arbitrarily pick one.
    with factory.begin() as s:
        contact = s.get(CRMContact, 1)
        contact.profile = {**contact.profile, "email": "mah@example.test"}
        grant = s.scalar(
            select(AlertDeskAccess).where(AlertDeskAccess.role == "end_user")
        )
        s.flush()
        grant.contact_version = contact.version
    token = magic(client, messages)
    result = post(client, "consume", token=token)
    assert result.status_code == 200 and len(result.json()["scopes"]) == 2
    assert client.cookies.get(ACCESS_COOKIE) is None
    scope = next(row for row in result.json()["scopes"] if "MAH" in row["label"])
    assert post(client, "scope", scope=scope["id"]).status_code == 200
    assert "MAH" in client.get("/alerts").text


def test_registration_origin_replay_and_fresh_signin_does_not_refresh_old_sessions(login):
    client, factory, messages = login
    old = secrets.token_urlsafe(32)
    with factory.begin() as s:
        grant = s.scalar(select(AlertDeskAccess).where(AlertDeskAccess.role == 'mah'))
        grant.session_hash = pilot.digest(old)
        grant.accepted_at = pilot.now() - timedelta(hours=1)
        grant.session_expires_at = pilot.now() + timedelta(hours=1)
    sign_in(client, messages)
    # A new device's mailbox proof must not turn an old legacy cookie into fresh proof.
    new = client.cookies.get(ACCESS_COOKIE)
    client.cookies.set(ACCESS_COOKIE, old, path='/alerts')
    assert post(client, 'register-options').status_code == 403
    client.cookies.set(ACCESS_COOKIE, new, path='/alerts')
    options = post(client, 'register-options').json()
    _, credential = registration(options, origin='https://attacker.example.test')
    assert post(client, 'register-finish', credential=credential).status_code == 403
    assert post(client, 'register-finish', credential=credential).status_code == 403
    with factory() as s:
        assert not s.scalar(select(AlertDeskParticipantPasskey))
        assert s.scalar(select(AlertDeskAccess).where(AlertDeskAccess.role == 'mah')).session_hash == pilot.digest(old)


def test_new_session_expiry_and_assignment_changes_are_rechecked(login):
    client, factory, messages = login
    sign_in(client, messages)
    raw = client.cookies.get(ACCESS_COOKIE)
    with factory.begin() as s:
        s.get(AlertDeskParticipantSession, pilot.digest(raw)).expires_at = pilot.now() - timedelta(seconds=1)
    assert 'Sign in to Alert Desk' in client.get('/alerts').text
    sign_in(client, messages)
    with factory.begin() as s:
        grant = s.scalar(select(AlertDeskAccess).where(AlertDeskAccess.role == 'mah'))
        contact = s.get(CRMContact, grant.contact_id)
        contact.profile = {**contact.profile, 'email': 'changed@example.test'}
    assert 'Sign in to Alert Desk' in client.get('/alerts').text
    assert client.get('/alerts/6').status_code == 404
