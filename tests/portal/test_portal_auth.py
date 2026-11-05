import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import select
from webauthn.helpers import bytes_to_base64url

from app.core.db.session import get_session
from app.domain.auth import service as auth
from app.domain.models import PortalUser
from app.portal import auth_access, auth_routes
from app.portal.routes import router as portal_router
from tests.portal.test_portal import portal  # noqa: F401 - shared fixture

ORIGIN = "http://localhost:8010"
HEADERS = {"Origin": ORIGIN}
RP_HASH = sha256(b"localhost").digest()


def client_data(kind, challenge):
    return json.dumps({"type": kind, "challenge": challenge, "origin": ORIGIN}).encode()


def test_passkey_enrolment_signin_role_guards_and_revocation(portal, monkeypatch):  # noqa: F811
    _, factory = portal
    settings = SimpleNamespace(
        portal_auth_enabled=True,
        portal_auth_origin=ORIGIN,
        environment="development",
        app_name="SMVS Operations",
    )
    monkeypatch.setattr(auth_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_access, "SessionFactory", factory)
    app = FastAPI()
    auth_access.install_portal_access(app, settings)
    app.mount(
        "/portal-static",
        StaticFiles(directory=Path("app/portal/static")),
        name="portal_static",
    )
    app.include_router(auth_routes.router)
    app.include_router(portal_router)
    app.get("/imports")(lambda: {"imports": True})

    def dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = dependency
    with factory() as session:
        invite = auth.invite_user(session, "nmvo@example.test", admin=False, nmvo=True)
        auth.invite_user(session, "admin@example.test", admin=True, nmvo=False)
        admin = session.scalar(
            select(PortalUser).where(PortalUser.email == "admin@example.test")
        )
        admin_session = auth.issue_token(
            session, "session", auth.SESSION_LIFETIME, user_id=admin.id
        )
        session.commit()
        nmvo_id = session.scalar(
            select(PortalUser.id).where(PortalUser.email == "nmvo@example.test")
        )

    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        assert client.get("/products").headers["location"] == "/auth/login"
        assert client.get("/auth/login").status_code == 200
        assert (
            client.post("/auth/enrol/options", json={"invitation": invite}).status_code
            == 403
        )
        options = client.post(
            "/auth/enrol/options", json={"invitation": invite}, headers=HEADERS
        ).json()
        private = ec.generate_private_key(ec.SECP256R1())
        key = private.public_key().public_numbers()
        cose = cbor2.dumps(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: key.x.to_bytes(32, "big"),
                -3: key.y.to_bytes(32, "big"),
            }
        )
        credential_id = b"virtual-credential"
        attested = (
            b"\x00" * 16 + len(credential_id).to_bytes(2, "big") + credential_id + cose
        )
        authenticator = RP_HASH + b"\x45" + bytes(4) + attested
        attestation = cbor2.dumps(
            {"fmt": "none", "attStmt": {}, "authData": authenticator}
        )
        identifier = bytes_to_base64url(credential_id)
        credential = {"id": identifier, "rawId": identifier, "type": "public-key"}
        registration = {
            "invitation": invite,
            "credential": {
                **credential,
                "response": {
                    "clientDataJSON": bytes_to_base64url(
                        client_data("webauthn.create", options["challenge"])
                    ),
                    "attestationObject": bytes_to_base64url(attestation),
                },
            },
        }
        result = client.post("/auth/enrol/finish", json=registration, headers=HEADERS)
        assert result.status_code == 200, result.text
        assert "HttpOnly" in result.headers["set-cookie"]
        assert (
            client.post(
                "/auth/enrol/options", json={"invitation": invite}, headers=HEADERS
            ).status_code
            == 403
        )
        products = client.get("/products")
        assert products.status_code == 200
        assert "Signed in as" in products.text and "nmvo@example.test" in products.text
        assert (
            'action="/auth/logout"' in products.text
            and ">Sign out</button>" in products.text
        )
        assert client.get("/admin/users").status_code == 403
        assert client.get("/imports").status_code == 403
        assert (
            client.post(
                "/auth/logout", data={"action": "logout"}, headers=HEADERS
            ).status_code
            == 303
        )
        assert client.get("/products").status_code == 303

        challenge = client.post(
            "/auth/signin/options", json={}, headers=HEADERS
        ).json()["challenge"]
        data = client_data("webauthn.get", challenge)
        authenticator = RP_HASH + b"\x05" + (1).to_bytes(4, "big")
        signature = private.sign(
            authenticator + sha256(data).digest(), ec.ECDSA(hashes.SHA256())
        )
        assertion = {
            "credential": {
                **credential,
                "response": {
                    "clientDataJSON": bytes_to_base64url(data),
                    "authenticatorData": bytes_to_base64url(authenticator),
                    "signature": bytes_to_base64url(signature),
                    "userHandle": options["user"]["id"],
                },
            }
        }
        assert (
            client.post(
                "/auth/signin/finish", json=assertion, headers=HEADERS
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/auth/signin/finish", json=assertion, headers=HEADERS
            ).status_code
            == 403
        )
        nmvo_session = client.cookies[auth.SESSION_COOKIE]

    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        client.cookies.set(auth.SESSION_COOKIE, admin_session)
        users = client.get("/admin/users")
        assert users.status_code == 200
        assert "<strong>admin@example.test</strong>" in users.text
        assert users.headers["referrer-policy"] == "same-origin"
        invitation = {"email": "invited@example.test", "nmvo": "yes"}
        assert (
            client.post(
                "/admin/users", data=invitation, headers={"Origin": "null"}
            ).status_code
            == 403
        )
        invited = client.post("/admin/users", data=invitation, headers=HEADERS)
        assert invited.status_code == 200
        assert "Invitation ready" in invited.text
        assert invited.headers["referrer-policy"] == "same-origin"
        assert client.get("/imports").status_code == 200
        assert client.get("/products").status_code == 403
        assert (
            client.post(
                f"/admin/users/{nmvo_id}", data={"command": "disable"}, headers=HEADERS
            ).status_code
            == 303
        )
        assert (
            client.post(
                f"/admin/users/{nmvo_id}", data={"command": "enable"}, headers=HEADERS
            ).status_code
            == 303
        )
        client.cookies.set(auth.SESSION_COOKIE, nmvo_session)
        assert client.get("/products").status_code == 303
