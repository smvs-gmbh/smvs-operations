# ruff: noqa: F811, SIM117
"""Permanent erasure must be authorised, atomic and safe against webhook replay."""

from types import SimpleNamespace

import pytest
from fastapi import Request
from sqlalchemy import func, select

from app.core.db.session import get_session
from app.domain.crm.deletion import erase_registration
from app.domain.models import (
    CRMContact,
    CRMDeletionEvent,
    CRMEndUser,
    EndUserRegistration,
    RegistrationEvent,
    RegistrationReceipt,
)
from app.portal import crm_routes, registration_routes
from tests.registration.test_connect import direct, request_data  # noqa: F401


def configure(web, factory, monkeypatch, admin=True):
    web.app.include_router(registration_routes.router)
    web.app.include_router(crm_routes.router)

    def identity(request: Request):
        request.state.portal_user = SimpleNamespace(
            id=1, email="admin@example.test", is_admin=admin, is_nmvo=True
        )
        with factory() as session:
            yield session

    web.app.dependency_overrides[get_session] = identity
    monkeypatch.setattr(registration_routes, "direct_delivery", lambda: True)


def accept(direct):
    raw, headers = request_data(direct)
    assert (
        direct.client.post(
            "/webhooks/tally/registrations", content=raw, headers=headers
        ).status_code
        == 200
    )
    with direct.factory() as s:
        row = s.scalar(select(EndUserRegistration))
        return row.id, row.version


def test_erasure_authorisation_confirmation_stale_and_replay(
    portal, direct, monkeypatch
):
    web, factory = portal
    identifier, version = accept(direct)
    configure(web, factory, monkeypatch, admin=False)
    path = f"/workflows/registrations/{identifier}/delete"
    data = {"version": str(version), "confirm_delete": "yes", "include_crm": "yes"}
    headers = {"origin": "http://testserver"}
    assert web.post(path, data=data, headers=headers).status_code == 403
    configure(web, factory, monkeypatch)
    page = web.get(f"/workflows/registrations/{identifier}")
    assert page.status_code == 200 and "Permanently delete registration" in page.text
    assert "Also delete the linked CRM End User" in page.text
    assert (
        web.post(path, data=data | {"version": "999"}, headers=headers).status_code
        == 409
    )
    assert (
        web.post(path, data=data | {"confirm_delete": ""}, headers=headers).status_code
        == 422
    )
    assert (
        web.post(path, data=data, headers=headers, follow_redirects=False).status_code
        == 303
    )
    with factory() as s:
        for model in (EndUserRegistration, RegistrationEvent, CRMContact, CRMEndUser):
            assert s.scalar(select(func.count()).select_from(model)) == 0
        assert s.scalar(select(func.count()).select_from(CRMDeletionEvent)) == 3
        receipt = s.scalar(select(RegistrationReceipt))
        assert receipt.mail_status == "deleted"
        assert (
            receipt.payload_ciphertext
            is receipt.token_digest
            is receipt.token_ciphertext
            is None
        )
    raw, signed = request_data(direct)
    assert (
        direct.client.post(
            "/webhooks/tally/registrations", content=raw, headers=signed
        ).status_code
        == 200
    )
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(EndUserRegistration)) == 0


def test_shared_contact_and_inflight_mail_block_erasure(direct):
    identifier, _ = accept(direct)
    with direct.factory.begin() as s:
        row = s.get(EndUserRegistration, identifier)
        shared = CRMEndUser(
            name="Other company", profile={"spoc_ids": [row.contact_id]}
        )
        s.add(shared)
    with direct.factory.begin() as s:
        with pytest.raises(ValueError, match="assigned"):
            erase_registration(
                s, s.get(EndUserRegistration, identifier), SimpleNamespace(id=1), True
            )
    with direct.factory.begin() as s:
        s.scalar(select(RegistrationReceipt)).mail_status = "sending"
    with direct.factory.begin() as s:
        with pytest.raises(ValueError, match="being processed"):
            erase_registration(
                s, s.get(EndUserRegistration, identifier), SimpleNamespace(id=1)
            )


def test_workflow_only_delete_keeps_crm_and_removes_dead_link(
    portal, direct, monkeypatch
):
    web, factory = portal
    identifier, version = accept(direct)
    configure(web, factory, monkeypatch)
    response = web.post(
        f"/workflows/registrations/{identifier}/delete",
        data={"version": version, "confirm_delete": "yes"},
        headers={"origin": "http://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with factory() as s:
        user = s.scalar(select(CRMEndUser))
        assert "registration_id" not in user.profile
        contact = s.scalar(select(CRMContact))
        assert contact is not None
    # Direct contact deletion removes its assignment but preserves the End User.
    assert (
        web.post(
            f"/crm/contacts/{contact.id}/delete",
            data={"version": contact.version, "confirm_delete": "yes"},
            headers={"origin": "http://testserver"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    with factory() as s:
        kept = s.get(CRMEndUser, user.id)
        assert kept is not None and kept.profile["spoc_ids"] == []
        assert s.get(CRMContact, contact.id) is None


def test_crm_deletion_review_offers_linked_registration_scope(
    portal, direct, monkeypatch
):
    web, factory = portal
    identifier, version = accept(direct)
    with factory() as s:
        registration = s.get(EndUserRegistration, identifier)
        user = s.get(CRMEndUser, registration.end_user_id)
        contact_id = registration.contact_id
    configure(web, factory, monkeypatch, admin=False)
    path = f"/crm/end-users/{user.id}/delete"
    assert web.get(path).status_code == 403
    configure(web, factory, monkeypatch)
    page = web.get(path)
    assert page.status_code == 200
    assert "Delete registration and linked CRM data" in page.text
    assert f'action="/workflows/registrations/{identifier}/delete"' in page.text
    assert f"/crm/contacts/{contact_id}" in page.text
    assert 'name="include_crm" value="yes"' in page.text
    # Old links/forms must also offer a usable review instead of a raw JSON error.
    blocked = web.post(
        path,
        data={"version": user.version, "confirm_delete": "yes"},
        headers={"origin": "http://testserver"},
    )
    assert blocked.status_code == 409
    assert blocked.headers["content-type"].startswith("text/html")
    assert "Delete registration and linked CRM data" in blocked.text
    with factory() as s:
        assert s.get(EndUserRegistration, identifier) is not None
        assert s.get(CRMEndUser, user.id) is not None
    erased = web.post(
        f"/workflows/registrations/{identifier}/delete",
        data={"version": version, "confirm_delete": "yes", "include_crm": "yes"},
        headers={"origin": "http://testserver"},
        follow_redirects=False,
    )
    assert erased.status_code == 303
    with factory() as s:
        assert s.get(EndUserRegistration, identifier) is None
        assert s.get(CRMEndUser, user.id) is None
        assert s.get(CRMContact, contact_id) is None
