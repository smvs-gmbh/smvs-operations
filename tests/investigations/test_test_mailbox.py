from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from app.portal import collaboration_routes, test_mailbox


@pytest.fixture
def mailbox(tmp_path, monkeypatch):
    settings = SimpleNamespace(environment="test", alert_desk_test_enabled=True)
    monkeypatch.setattr(test_mailbox, "get_settings", lambda: settings)
    monkeypatch.setattr(collaboration_routes, "get_settings", lambda: settings)
    monkeypatch.setenv("SMVS_TEST_ROOT", str(tmp_path))
    monkeypatch.setenv("ALERT_DESK_PILOT_SECRET", "test-mail-secret-" * 3)
    monkeypatch.setenv("ALERT_DESK_PUBLIC_ORIGIN", "https://connect-test.example.test")
    folder = tmp_path / "private/mail"
    folder.mkdir(parents=True)
    app = FastAPI()
    app.mount("/portal-static", StaticFiles(directory="app/portal/static"), name="portal_static")
    app.include_router(collaboration_routes.router)

    @app.middleware("http")
    async def identity(request, call_next):
        staff = request.headers.get("x-test-role", "staff") == "staff"
        request.state.portal_auth_enabled = True
        request.state.portal_user = SimpleNamespace(is_admin=staff, is_nmvo=staff, email="staff@example.test")
        return await call_next(request)

    return TestClient(app), folder, settings


def test_private_mailbox_displays_captured_invitation_and_code_without_active_html(mailbox):
    client, folder, _ = mailbox
    token = "t" * 43
    identifier = "a" * 32
    (folder / (identifier + ".eml")).write_text(
        "To: end_user@example.test\nSubject: Invitation <script>bad()</script>\n"
        "Content-Type: text/plain; charset=utf-8\n\n"
        "https://connect-test.example.test/alerts/access#" + token + "\n<script>bad()</script>"
    )
    index = client.get("/workflows/alert-desk/mailbox")
    assert index.status_code == 200 and "end_user@example.test" in index.text
    assert token not in index.text
    detail = client.get("/workflows/alert-desk/mailbox/" + identifier)
    assert detail.status_code == 200
    assert "Open participant invitation" in detail.text
    assert "<script>bad()" not in detail.text and "&lt;script&gt;bad()" in detail.text
    assert detail.headers["cache-control"] == "no-store"
    assert detail.headers["referrer-policy"] == "no-referrer"
    (folder / ("b" * 32 + ".eml")).write_text("Subject: Verification code\n\nYour code is 123456.")
    assert "123456" in client.get("/workflows/alert-desk/mailbox/" + "b" * 32).text


def test_mailbox_requires_test_staff_and_refuses_paths_symlinks_and_foreign_links(mailbox):
    client, folder, settings = mailbox
    base = "/workflows/alert-desk/mailbox"
    assert client.get(base, headers={"x-test-role": "participant"}).status_code == 403
    settings.environment = "production"
    assert client.get(base).status_code == 404
    settings.environment = "development"
    assert client.get(base).status_code == 404
    settings.environment = "test"
    settings.alert_desk_test_enabled = False
    assert client.get(base).status_code == 404
    settings.alert_desk_test_enabled = True
    assert client.get(base + "/invalid").status_code == 404
    outside = folder.parent / "secret.eml"
    outside.write_text("Subject: secret\n\nsecret")
    identifier = "c" * 32
    (folder / (identifier + ".eml")).symlink_to(outside)
    assert client.get(base + "/" + identifier).status_code == 404
    (folder / (identifier + ".eml")).unlink()
    (folder / (identifier + ".eml")).write_text("Subject: Test\n\nhttps://attacker.test/alerts/access#" + "t" * 43)
    assert "Open participant invitation" not in client.get(base + "/" + identifier).text
