from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.alert_desk.schema import PUBLIC_ORIGIN
from app.alert_desk.test_workspace import create_workspace, fixture_database
from app.alert_desk.web import ACCESS_COOKIE
from app.alert_desk.web import create_app as public_app
from app.domain.investigations import pilot
from app.domain.investigations.pilot_api import create_app
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskCommentTemplate,
    AlertDeskCommentTemplateEvent,
    AlertDeskEvent,
    CRMContact,
    CRMEndUser,
)

SECRET = "test-comment-templates-only-" * 2
TOKENS = {"end_user": "e" * 43, "mah": "m" * 43}


@pytest.fixture
def templates(tmp_path):
    engine, factory = fixture_database(tmp_path / "templates.db")
    create_workspace(factory)
    with factory.begin() as session:
        for grant in session.scalars(select(AlertDeskAccess)):
            grant.session_hash = pilot.digest(TOKENS[grant.role])
    app = create_app(factory, SECRET)
    client = TestClient(
        app, base_url="http://127.0.0.1:8015", client=("127.0.0.1", 1234)
    )
    try:
        yield client, factory, app
    finally:
        client.close()
        engine.dispose()


def headers(role="end_user"):
    return {"Authorization": "Bearer " + SECRET, "X-Case-Session": TOKENS[role]}


def endpoint(case=1):
    return f"/access/alerts/{case}/comment-templates"


def create(client, **changes):
    return client.post(
        endpoint(),
        headers=headers(),
        json={
            "command": "create",
            "name": "Scanner",
            "text": "Scanner geprüft.",
            **changes,
        },
    )


def test_private_scope_crud_cross_case_and_transactional_history(templates):
    client, factory, _ = templates
    response = create(client)
    assert response.status_code == 200
    original = response.json()["template"]
    identifier = original["id"]
    assert (
        client.get(endpoint(2), headers=headers()).json()["templates"][0]["id"]
        == identifier
    )
    assert client.get(endpoint(), headers=headers("mah")).json() == {"templates": []}
    assert (
        client.get(endpoint() + f"/{identifier}", headers=headers("mah")).status_code
        == 404
    )
    for command in ["update", "delete", "insert"]:
        assert (
            client.post(
                endpoint(),
                headers=headers("mah"),
                json={
                    "command": command,
                    "template_id": identifier,
                    "version": 1,
                    "name": "Stolen",
                    "text": "Other",
                },
            ).status_code
            == 404
        )
    assert create(client, name="  SCANNER  ").status_code == 409
    inserted = client.post(
        endpoint(),
        headers=headers(),
        json={"command": "insert", "template_id": identifier, "version": 1},
    )
    assert inserted.json()["template"]["text"] == original["text"]
    changed = client.post(
        endpoint(),
        headers=headers(),
        json={
            "command": "update",
            "template_id": identifier,
            "version": 1,
            "name": "Updated",
            "text": "Checked again.",
        },
    )
    assert changed.status_code == 200 and changed.json()["template"]["version"] == 2
    for command in ["update", "delete", "insert"]:
        assert (
            client.post(
                endpoint(),
                headers=headers(),
                json={
                    "command": command,
                    "template_id": identifier,
                    "version": 1,
                    "name": "Stale",
                    "text": "Stale",
                },
            ).status_code
            == 409
        )
    # Reissued sessions keep stable ownership, without trusting the old token.
    with factory.begin() as session:
        grant = session.scalar(
            select(AlertDeskAccess).where(AlertDeskAccess.role == "end_user")
        )
        grant.session_hash = pilot.digest("n" * 43)
    new_headers = {**headers(), "X-Case-Session": "n" * 43}
    assert client.get(endpoint(), headers=headers()).status_code == 404
    assert (
        client.get(endpoint(), headers=new_headers).json()["templates"][0]["id"]
        == identifier
    )
    assert (
        client.post(
            endpoint(),
            headers=new_headers,
            json={"command": "delete", "template_id": identifier, "version": 2},
        ).status_code
        == 200
    )
    assert client.get(endpoint(), headers=new_headers).json() == {"templates": []}
    assert (
        client.get(endpoint() + f"/{identifier}", headers=new_headers).status_code
        == 404
    )
    assert (
        client.post(
            endpoint(),
            headers=new_headers,
            json={"command": "create", "name": "Updated", "text": "Reused name."},
        ).status_code
        == 200
    )
    with factory() as session:
        events = session.scalars(
            select(AlertDeskCommentTemplateEvent).order_by(
                AlertDeskCommentTemplateEvent.id
            )
        ).all()
        assert [e.action for e in events] == [
            "create",
            "insert",
            "update",
            "delete",
            "create",
        ]
        assert events[0].data["after"]["text"] == "Scanner geprüft."
        assert events[2].data["before"]["name"] == "Scanner"
        assert session.scalar(select(func.count()).select_from(AlertDeskEvent)) == 0


def test_same_organisation_other_contact_and_revocation_are_denied(templates):
    client, factory, _ = templates
    identifier = create(client).json()["template"]["id"]
    with factory.begin() as session:
        grant = session.scalar(
            select(AlertDeskAccess).where(AlertDeskAccess.role == "end_user")
        )
        # Use a second verified contact in the same organisation, not merely another role.
        contact = CRMContact(
            airtable_id="template-test-second",
            label="Second contact",
            profile={"email": "second@example.test"},
            version=1,
        )
        session.add(contact)
        session.flush()
        crm = session.get(CRMEndUser, grant.crm_organisation_id)
        crm.profile = {
            **crm.profile,
            "alert_contact_ids": [*crm.profile["alert_contact_ids"], contact.id],
        }
        session.add(
            AlertDeskAccess(
                role=grant.role,
                crm_organisation_id=crm.id,
                contact_id=contact.id,
                contact_version=1,
                scope_key=grant.scope_key,
                invited_by=grant.invited_by,
                invited_at=pilot.now(),
                sent_at=pilot.now(),
                accepted_at=pilot.now(),
                invite_expires_at=pilot.now(),
                session_hash=pilot.digest("s" * 43),
                session_expires_at=pilot.now() + timedelta(hours=1),
                attempts_left=0,
            )
        )
    second = {**headers(), "X-Case-Session": "s" * 43}
    assert client.get(endpoint(), headers=second).json() == {"templates": []}
    assert client.get(endpoint() + f"/{identifier}", headers=second).status_code == 404
    with factory.begin() as session:
        grant = session.scalar(
            select(AlertDeskAccess).where(
                AlertDeskAccess.session_hash == pilot.digest("s" * 43)
            )
        )
        grant.revoked_at = pilot.now()
    assert client.get(endpoint(), headers=second).status_code == 404
    assert client.get(endpoint(9999), headers=headers()).status_code == 404


def test_gateway_requires_verified_session_origin_and_bounded_valid_commands(templates):
    _, _, private = templates
    with TestClient(
        public_app(SECRET, transport=httpx.ASGITransport(app=private)),
        base_url=PUBLIC_ORIGIN,
        client=("127.0.0.1", 1234),
    ) as web:
        path = "/alerts/1/comment-templates"
        assert web.get(path).status_code == 404
        web.cookies.set(ACCESS_COOKIE, TOKENS["end_user"], path="/alerts")
        assert (
            web.post(
                path, json={"command": "create", "name": "One", "text": "Text"}
            ).status_code
            == 403
        )
        bad = [
            {"command": "create", "name": "", "text": "Text"},
            {"command": "create", "name": "One", "text": "x" * 1001},
            {"command": "create", "name": "One", "text": "Text", "owner": 1},
            {"command": "delete", "template_id": 1},
            {"command": "insert", "template_id": 1, "version": 0},
            {"command": "create", "name": "x" * 81, "text": "Text"},
        ]
        for body in bad:
            assert (
                web.post(path, headers={"Origin": PUBLIC_ORIGIN}, json=body).status_code
                == 422
            )
        result = web.post(
            path,
            headers={"Origin": PUBLIC_ORIGIN},
            json={"command": "create", "name": "Own", "text": "Own text"},
        )
        assert result.status_code == 200
        assert web.get(path).json()["templates"][0]["name"] == "Own"
        assert (
            web.get(path + "/" + str(result.json()["template"]["id"])).json()[
                "template"
            ]["text"]
            == "Own text"
        )


def test_submitted_comment_is_not_changed_by_template_update_or_deletion(templates):
    client, factory, _ = templates
    item = create(client).json()["template"]
    case = client.get("/access/alerts/1", headers=headers()).json()
    finding = {
        "publication": 1,
        "basis": case["basis"],
        "submission_key": str(uuid4()),
        "finding": "investigating",
        "comparison": "not_checked",
        "comment": item["text"],
    }
    assert (
        client.post(
            "/access/alerts/1/findings", headers=headers(), json=finding
        ).status_code
        == 200
    )
    assert (
        client.post(
            endpoint(),
            headers=headers(),
            json={
                "command": "update",
                "template_id": item["id"],
                "version": 1,
                "name": "Changed",
                "text": "Different",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            endpoint(),
            headers=headers(),
            json={"command": "delete", "template_id": item["id"], "version": 2},
        ).status_code
        == 200
    )
    with factory() as session:
        event = session.scalar(
            select(AlertDeskEvent).where(AlertDeskEvent.kind == "Findings submitted")
        )
        assert event.data["comment"] == "Scanner geprüft."


def test_quota_and_audit_failure_do_not_leave_partial_templates(templates, monkeypatch):
    client, factory, _ = templates
    for n in range(50):
        assert create(client, name=f"Template {n}").status_code == 200
    assert create(client, name="Overflow").status_code == 422
    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(AlertDeskCommentTemplate))
            == 50
        )
        assert (
            session.scalar(
                select(func.count()).select_from(AlertDeskCommentTemplateEvent)
            )
            == 50
        )
    # If retaining the transactional audit row fails, the edit must roll back.
    from sqlalchemy import event

    def refuse(mapper, connection, target):
        raise RuntimeError("Synthetic audit failure")

    event.listen(AlertDeskCommentTemplateEvent, "before_insert", refuse)
    try:
        with pytest.raises(RuntimeError, match="Synthetic audit failure"):
            client.post(
                endpoint(),
                headers=headers(),
                json={
                    "command": "update",
                    "template_id": 1,
                    "version": 1,
                    "name": "Should roll back",
                    "text": "Changed",
                },
            )
    finally:
        event.remove(AlertDeskCommentTemplateEvent, "before_insert", refuse)
    assert (
        client.get(endpoint() + "/1", headers=headers()).json()["template"]["name"]
        == "Template 0"
    )


@pytest.mark.parametrize(
    "revocation", ["expired", "contact_changed", "assignment_removed"]
)
def test_template_actions_respect_current_access_not_just_an_old_cookie(
    templates, revocation
):
    client, factory, _ = templates
    item = create(client).json()["template"]
    with factory.begin() as session:
        grant = session.scalar(
            select(AlertDeskAccess).where(AlertDeskAccess.role == "end_user")
        )
        if revocation == "expired":
            grant.session_expires_at = pilot.now() - timedelta(seconds=1)
        elif revocation == "contact_changed":
            session.get(CRMContact, grant.contact_id).label = "Changed contact"
        else:
            crm = session.get(CRMEndUser, grant.crm_organisation_id)
            crm.profile = {**crm.profile, "alert_contact_ids": []}
    assert client.get(endpoint(), headers=headers()).status_code == 404
    assert (
        client.post(
            endpoint(),
            headers=headers(),
            json={"command": "delete", "template_id": item["id"], "version": 1},
        ).status_code
        == 404
    )
    with factory() as session:
        assert session.get(AlertDeskCommentTemplate, item["id"]).deleted_at is None
