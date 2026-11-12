# ruff: noqa: F811
"""Participant preview minimises data and traces guidance without publishing work."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import Request
from sqlalchemy import func, select

from app.core.db.session import get_session
from app.domain.exceptions.mapping import publish_exceptions
from app.domain.investigations.preview import (
    GUIDANCE_VERSION,
    batch_reference,
    participant_projection,
)
from app.domain.models import (
    ExceptionReview,
    NMVSException,
    PackAuditRequest,
    UploadRequest,
)
from app.portal.collaboration_routes import router
from tests.integration.exceptions.test_exceptions import NS, acquire, alert, page
from tests.portal.test_exceptions import exceptions_portal  # noqa: F401
from tests.portal.test_portal import portal  # noqa: F401


def record(**values):
    return SimpleNamespace(
        **{
            "unique_alert_id": "CH-fixture-1",
            "alert_at": datetime(2026, 11, 10, 10, tzinfo=UTC),
            "error_code": "A2",
            "error_message": "PRIVATE SOURCE MESSAGE",
            "gtin14": "04006381333931",
            "product_code": "4006381333931",
            "provided_batch": "Batch-001",
            "stored_batch": "Batch-002",
            "serial_number": "PRIVATE-SERIAL-12345678901234",
            "evidence": {
                "attemptedOperation": "EXPORTED",
                "contactEmail": "private@example.test",
                "providedExpiry": "PRIVATE EXPIRY",
            },
            **values,
        }
    )


@pytest.mark.parametrize("code", ["A2", "A3", "A52", "A68"])
def test_identifier_guidance_and_projection_minimisation(code):
    source = record(error_code=code)
    result = participant_projection(
        source, name="Swiss source name", holder="Swiss holder"
    )
    encoded = json.dumps(result)
    assert result["guidance_version"] == GUIDANCE_VERSION
    assert {"identifier-comparison", "manual-check", "scanner", "software"} <= {
        q["id"] for q in result["checks"]
    }
    assert "Swiss source name" in encoded and "04006381333931" in encoded
    assert source.serial_number in encoded
    assert {
        "label": "Transmitted serial length",
        "value": str(len(source.serial_number)),
    } in result["facts"]
    for forbidden in [
        source.error_message,
        "private@example.test",
        "PRIVATE EXPIRY",
        "payload_hash",
        "organisation_id",
        "source_location_id",
    ]:
        assert forbidden not in encoded
    assert "no cause has been confirmed" in result["observation_note"].lower()
    assert "closure decision" in result["feedback"]


@pytest.mark.parametrize("code", ["A7", "A24"])
def test_state_alerts_do_not_prompt_manual_reentry(code):
    result = participant_projection(record(error_code=code), workflow="wholesaler")
    ids = {q["id"] for q in result["checks"]}
    assert {
        "procedural",
        "different-location",
        "wholesaler-role",
        "wholesaler-routing",
    } <= ids
    assert not {"manual-check", "identifier-comparison"} & ids
    assert any(q["source"] == "3.4" for q in result["checks"])


def test_serial_is_preserved_but_unknown_operation_and_error_are_not_leaked():
    result = participant_projection(
        record(
            serial_number="1234",
            error_code="PRIVATE UNMAPPED ERROR",
            evidence={"attemptedOperation": "PRIVATE UNKNOWN OPERATION"},
        )
    )
    raw = json.dumps(result)
    assert "1234" in raw and "PRIVATE" not in raw
    assert any(q["id"] == "nmvo-review" for q in result["checks"])
    with pytest.raises(ValueError):
        participant_projection(record(), workflow="mah")


@pytest.fixture
def preview_portal(exceptions_portal):
    web, factory = exceptions_portal
    web.app.include_router(router)

    def identity(request: Request):
        role = request.headers.get("x-test-role")
        if role:
            request.state.portal_user = SimpleNamespace(
                id=1, is_nmvo=role == "nmvo", is_admin=role == "admin"
            )
        with factory() as s:
            yield s

    web.app.dependency_overrides[get_session] = identity
    publish_exceptions(
        factory,
        acquire(
            factory,
            [
                page(
                    [
                        alert(
                            serialNumber="PRIVATE-SERIAL-012345678901234",
                            errorMessage="PRIVATE INTERNAL MESSAGE",
                            isIntermarket=False,
                            attemptedOperation="EXPORTED",
                        )
                    ]
                )
            ],
        ),
        NS,
    )
    with factory() as s:
        identifier = s.scalar(select(NMVSException.id))
    return web, factory, identifier


def test_preview_is_staff_only_read_only_and_keeps_source_and_requests_unchanged(
    preview_portal,
):
    web, factory, identifier = preview_portal
    url = f"/exceptions/{identifier}/participant-preview"
    assert web.get(url).status_code == 403
    assert web.get(url, headers={"x-test-role": "mah"}).status_code == 403
    with factory() as s:
        source_hash = s.get(NMVSException, identifier).payload_hash
    for workflow in ["pharmacy", "wholesaler"]:
        response = web.get(
            url, params={"workflow": workflow}, headers={"x-test-role": "nmvo"}
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert (
            "Your checks" in response.text
            and "within two working days" in response.text
        )
        assert "PRIVATE-SERIAL-012345678901234" in response.text
        assert "PRIVATE INTERNAL MESSAGE" not in response.text
        assert "WRONG NMVS NAME" not in response.text
        assert ("Wholesaler process" in response.text) == (workflow == "wholesaler")
    assert web.get(url, headers={"x-test-role": "admin"}).status_code == 200
    assert (
        web.get(url + "?workflow=mah", headers={"x-test-role": "nmvo"}).status_code
        == 422
    )
    assert web.post(url, headers={"x-test-role": "nmvo"}).status_code == 405
    assert (
        web.get(
            "/exceptions/999999/participant-preview", headers={"x-test-role": "nmvo"}
        ).status_code
        == 404
    )
    with factory() as s:
        assert s.get(NMVSException, identifier).payload_hash == source_hash
        for model in (ExceptionReview, PackAuditRequest, UploadRequest):
            assert s.scalar(select(func.count()).select_from(model)) == 0


def test_internal_assessment_is_not_automatically_shared_and_market_review_stays_internal(
    preview_portal,
):
    web, factory, identifier = preview_portal
    from app.integration.artifacts.storage import utcnow

    with factory.begin() as s:
        source = s.get(NMVSException, identifier)
        source.is_intermarket = 1
        source.source_market = "DE"
        s.add(
            ExceptionReview(
                exception_id=identifier,
                status="open",
                basis_payload_hash="0" * 64,
                findings="PRIVATE STAFF FINDINGS",
                cause="PRIVATE STAFF CONCLUSION",
                next_action="",
                review_reason="PRIVATE STAFF EMAIL",
                updated_at=utcnow(),
            )
        )
    response = web.get(
        f"/exceptions/{identifier}/participant-preview", headers={"x-test-role": "nmvo"}
    )
    assert response.status_code == 200
    assert "Market responsibility needs NMVO review" in response.text
    assert "source changed" in response.text.lower()
    for marker in [
        "PRIVATE STAFF FINDINGS",
        "PRIVATE STAFF CONCLUSION",
        "PRIVATE STAFF EMAIL",
    ]:
        assert marker not in response.text


def test_batch_reference_is_allowlisted_and_keeps_source_format_codes():
    batch = SimpleNamespace(
        batch_code="00123456",
        evidence={
            "Min SN Length": "14",
            "Max SN Length": "14",
            "SN Format": "N",
            "Batch Length": "8",
            "Batch Format": "N",
            "Markets": "CH, FR",
            "Number Of Packs": "1199",
            "INTERNAL": "PRIVATE",
        },
    )
    reference = batch_reference(batch, role="Stored batch")
    raw = json.dumps(reference)
    assert reference["batch"] == "00123456"
    assert reference["role"] == "Stored batch"
    assert len(reference["fields"]) == 6
    assert "PRIVATE" not in raw and "1199" not in raw
    result = participant_projection(record(error_code="A7"), batches=[reference])
    assert result["batch_references"] == [reference]
    assert "Root cause on my side" in result["assessment"]["choices"]
    assert "does not confirm" in result["assessment"]["instruction"]
    assert participant_projection(record(error_code="A3"))["assessment"] is None


def test_preview_batch_reference_requires_exact_observed_source_match(preview_portal):
    from app.domain.mapping import publish
    from app.domain.models import Batch
    from tests.domain.test_mapping import seed

    web, factory, identifier = preview_portal
    publish(factory, *seed(factory), NS)
    with factory.begin() as session:
        batch = session.scalar(select(Batch).where(Batch.batch_code == "Lot-001"))
        batch_id = batch.id
        batch.evidence = {"Min SN Length": "14", "SN Format": "N"}
    url = f"/exceptions/{identifier}/participant-preview"
    headers = {"x-test-role": "nmvo"}
    html = web.get(url, headers=headers).text
    assert "Batch reference from Snapshot" in html
    assert "Stored batch · Lot-001" in html
    assert "Provided batch · BAD" not in html
    assert "Minimum serial length" in html
    with factory.begin() as session:
        session.get(Batch, batch_id).batch_code = "lot-001"
    assert "Batch reference from Snapshot" not in web.get(url, headers=headers).text
    with factory.begin() as session:
        batch = session.get(Batch, batch_id)
        batch.batch_code = "Lot-001"
        batch.is_observed = 0
    assert "Batch reference from Snapshot" not in web.get(url, headers=headers).text


def test_prepare_evidence_is_explicit_authorised_and_reuses_queue(
    preview_portal, monkeypatch
):
    from app.core.db.models import ImportMutex
    from app.domain.pack_audit.service import QUEUE_LOCK
    from app.portal import collaboration_routes

    web, factory, identifier = preview_portal
    monkeypatch.setattr(collaboration_routes, "SessionFactory", factory)
    with factory.begin() as session:
        session.add(ImportMutex(import_key=QUEUE_LOCK))
        record = session.get(NMVSException, identifier)
        record.error_code = "A7"
        version = record.payload_hash
    url = f"/exceptions/{identifier}/prepare-evidence"
    data = {"source_version": version}
    assert web.post(url, data=data).status_code == 403
    assert web.post(url, data=data, headers={"x-test-role": "mah"}).status_code == 403
    assert web.post(url, data=data, headers={"x-test-role": "nmvo"}).status_code == 403
    headers = {"x-test-role": "nmvo", "origin": "http://testserver"}
    assert (
        web.post(url, data={"source_version": "stale"}, headers=headers).status_code
        == 409
    )
    for _ in range(2):
        response = web.post(url, data=data, headers=headers, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/exceptions/{identifier}/analysis"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PackAuditRequest)) == 1
        task = session.scalar(select(PackAuditRequest))
        assert task.status == "queued" and task.attempt_count == 0
    assert (
        "already queued or running"
        in web.get(
            f"/exceptions/{identifier}/participant-preview", headers=headers
        ).text
    )


def test_prepare_evidence_does_not_request_a2_or_imt(preview_portal, monkeypatch):
    from app.portal import collaboration_routes

    web, factory, identifier = preview_portal

    def forbidden(*args, **kwargs):
        raise AssertionError("No report request expected")

    monkeypatch.setattr(collaboration_routes, "request_report", forbidden)
    headers = {"x-test-role": "nmvo", "origin": "http://testserver"}
    url = f"/exceptions/{identifier}/prepare-evidence"
    with factory() as session:
        version = session.get(NMVSException, identifier).payload_hash
    assert (
        web.post(url, data={"source_version": version}, headers=headers).status_code
        == 409
    )
    with factory.begin() as session:
        record = session.get(NMVSException, identifier)
        record.error_code, record.is_intermarket = "A7", 1
    assert (
        web.post(url, data={"source_version": version}, headers=headers).status_code
        == 409
    )


def test_organisation_invitation_and_case_scope(preview_portal, monkeypatch):
    import re
    from datetime import timedelta
    from uuid import uuid4

    import httpx
    from fastapi.testclient import TestClient

    from app.alert_desk.schema import PUBLIC_ORIGIN
    from app.alert_desk.web import ACCESS_COOKIE
    from app.alert_desk.web import create_app as public_app
    from app.core.db.models import ImportMutex
    from app.domain.investigations.pilot_api import create_app as private_app
    from app.domain.mapping import publish
    from app.domain.models import (
        AlertDeskAccess,
        AlertDeskEvent,
        AlertDeskExportAttribution,
        CRMContact,
        CRMEndUser,
        CRMMah,
        PortalUser,
    )
    from app.domain.participants.mapping import MUTEX, publish_participants
    from app.integration.artifacts.storage import utcnow
    from app.portal import collaboration_routes
    from tests.domain.test_mapping import seed
    from tests.domain.test_participants import source

    web, factory, identifier = preview_portal
    secret = "test-only-pilot-secret-" * 2
    monkeypatch.setenv("ALERT_DESK_PILOT_SECRET", secret)
    monkeypatch.setattr(
        collaboration_routes,
        "get_settings",
        lambda: SimpleNamespace(
            environment="development", portal_auth_origin="http://testserver"
        ),
    )
    with factory.begin() as session:
        session.add(ImportMutex(import_key=MUTEX))
        session.add(
            PortalUser(email="nmvo@example.test", handle="pilot", is_nmvo=1, is_admin=0)
        )
        case = session.get(NMVSException, identifier)
        case.error_code = "A3"
        case.organisation_id = "Org-001"
        case.source_location_id = "Loc-001"
        version = case.payload_hash
        fields = {
            column.key: getattr(case, column.key)
            for column in NMVSException.__table__.columns
            if column.key != "id"
        }
        session.add(
            NMVSException(
                **{
                    **fields,
                    "alert_key": "0" * 64,
                    "unique_alert_id": "CH-A52-OTHER-CASE",
                    "error_code": "A52",
                    "gtin14": None,
                }
            )
        )
        session.add(
            NMVSException(
                **{
                    **fields,
                    "alert_key": "1" * 64,
                    "unique_alert_id": "DE-FOREIGN",
                    "source_market": "DE",
                    "gtin14": None,
                }
            )
        )
        for key, alert_id, batch in [
            ("2", "CH-IMT-ATTRIBUTED", "KNOWN"),
            ("3", "CH-IMT-OTHER-BATCH", "OTHER"),
            ("4", "CH-IMT-SAME-BATCH", "KNOWN"),
        ]:
            session.add(
                NMVSException(
                    **{
                        **fields,
                        "alert_key": key * 64,
                        "unique_alert_id": alert_id,
                        "source_market": "DE",
                        "source_location_id": "foreign-location",
                        "organisation_id": None,
                        "provided_batch": batch,
                        "error_code": "A7",
                        "business_process": "National System Intermarket",
                        "evidence": {"attemptedOperation": "EXPORTED"},
                    }
                )
            )
    publish_participants(factory, source(factory), NS)
    publish(factory, *seed(factory), NS)
    with factory.begin() as session:
        alert_contact = CRMContact(
            airtable_id="alert",
            label="Alert SPOC",
            profile={"email": "alert@example.test"},
        )
        spoc = CRMContact(
            airtable_id="spoc",
            label="General SPOC",
            profile={"email": "general@example.test"},
        )
        mah_contact = CRMContact(
            airtable_id="mah", label="MAH SPOC", profile={"email": "mah@example.test"}
        )
        session.add_all([alert_contact, spoc, mah_contact])
        session.flush()
        session.add(
            CRMEndUser(
                name="Synthetic Pharmacy",
                organisation_id=1,
                profile={
                    "alert_contact_ids": [alert_contact.id],
                    "spoc_contact_ids": [spoc.id],
                },
            )
        )
        session.add(
            CRMMah(
                name="CRM MAH",
                gln="1234567890128",
                contract_status="unknown",
                created_at=utcnow(),
                updated_at=utcnow(),
                profile={"alert_contact_ids": [mah_contact.id]},
            )
        )
        foreign_id = session.scalar(
            select(NMVSException.id).where(
                NMVSException.unique_alert_id == "DE-FOREIGN"
            )
        )
        other_id = session.scalar(
            select(NMVSException.id).where(
                NMVSException.unique_alert_id == "CH-A52-OTHER-CASE"
            )
        )

        attributed = session.scalar(
            select(NMVSException).where(
                NMVSException.unique_alert_id == "CH-IMT-ATTRIBUTED"
            )
        )
        attributed_id = attributed.id
        end_user_id = session.scalar(select(CRMEndUser.id))
        session.add(
            AlertDeskExportAttribution(
                anchor_exception_id=attributed_id,
                end_user_id=end_user_id,
                source_namespace=NS,
                source_market="DE",
                source_location_id="foreign-location",
                gtin14=attributed.gtin14,
                batch="KNOWN",
                from_at=attributed.alert_at - timedelta(hours=1),
                until_at=attributed.alert_at + timedelta(hours=1),
                reason="Confirmed synthetic attribution",
                confirmed_at=utcnow(),
            )
        )

    sent = {}
    codes = {}
    monkeypatch.setattr(
        collaboration_routes.pilot_mail,
        "send_access",
        lambda address, token: sent.update({address: token}),
    )
    monkeypatch.setattr(
        collaboration_routes.pilot_mail,
        "send_code",
        lambda address, code: codes.update({address: code}),
    )
    private = private_app(factory, secret)
    public = public_app(secret, transport=httpx.ASGITransport(app=private))
    nmvo = {"x-test-role": "nmvo", "origin": "http://testserver"}
    browser = {"origin": PUBLIC_ORIGIN}
    url = "/workflows/alert-desk"
    assert web.get(url).status_code == 403
    review = web.get(url, headers=nmvo)
    assert "Not invited" in review.text and "general@example.test" not in review.text
    choices = re.findall(r'value="((?:end_user|mah):[^"]+)"', review.text)
    assert len(choices) == 2 and sent == {}
    data = {"selected": ",".join(choices)}
    assert (
        web.post(
            url + "/send", data=data, headers={**nmvo, "x-test-role": "mah"}
        ).status_code
        == 403
    )
    assert "2 of 2 selected" in web.post(url + "/send", data=data, headers=nmvo).text
    assert set(sent) == {"alert@example.test", "mah@example.test"}
    assert "0 of 2 selected" in web.post(url + "/send", data=data, headers=nmvo).text

    def browser_client():
        return TestClient(public, base_url=PUBLIC_ORIGIN, client=("127.0.0.1", 50000))

    with browser_client() as end_user, browser_client() as other_browser:
        unavailable = end_user.get(f"/alerts/{identifier}")
        assert unavailable.status_code == 404
        assert "ask SMVS for a new invitation" in unavailable.text
        assert 'href="/alerts"' in unavailable.text
        response = end_user.post(
            "/alerts/access/challenge",
            json={"token": sent["alert@example.test"]},
            headers=browser,
        )
        assert (
            response.status_code == 200 and "HttpOnly" in response.headers["set-cookie"]
        )
        assert "PRIVATE-SERIAL" not in end_user.get("/alerts").text
        code = codes["alert@example.test"]
        wrong = "000000" if code != "000000" else "000001"
        assert (
            end_user.post(
                "/alerts/access/verify", json={"code": wrong}, headers=browser
            ).status_code
            == 422
        )
        assert (
            other_browser.post(
                "/alerts/access/verify", json={"code": code}, headers=browser
            ).status_code
            == 422
        )
        assert (
            end_user.post(
                "/alerts/access/verify", json={"code": code}, headers=browser
            ).status_code
            == 200
        )
        assert (
            end_user.post(
                "/alerts/access/challenge",
                json={"token": sent["alert@example.test"]},
                headers=browser,
            ).status_code
            == 404
        )
        listing = end_user.get("/alerts").text
        assert "CH-A52-OTHER-CASE" in listing and "DE-FOREIGN" not in listing
        assert "CH-IMT-ATTRIBUTED" in listing and "CH-IMT-OTHER-BATCH" not in listing
        imt_page = end_user.get(f"/alerts/{attributed_id}")
        assert imt_page.status_code == 200 and "Synthetic Pharmacy" in imt_page.text
        assert "Your investigation" in imt_page.text
        assert "Update findings for this batch (2 alerts)" in imt_page.text
        batch_revision = re.search(
            r'data-batch-revision="([^"]+)"', imt_page.text
        ).group(1)
        with factory() as session:
            sibling_id = session.scalar(
                select(NMVSException.id).where(
                    NMVSException.unique_alert_id == "CH-IMT-SAME-BATCH"
                )
            )
            unrelated_id = session.scalar(
                select(NMVSException.id).where(
                    NMVSException.unique_alert_id == "CH-IMT-OTHER-BATCH"
                )
            )
        bulk = {
            "publication": attributed_id,
            "basis": version,
            "submission_key": str(uuid4()),
            "finding": "procedural",
            "capa": "planned",
            "batch_revision": batch_revision,
        }
        endpoint = f"/alerts/{attributed_id}/findings"
        assert (
            end_user.post(
                endpoint, json={**bulk, "batch_revision": "0" * 64}, headers=browser
            ).status_code
            == 409
        )
        interim = {
            **bulk,
            "submission_key": str(uuid4()),
            "finding": "investigating",
            "capa": None,
        }
        for _ in range(2):
            assert end_user.post(endpoint, json=interim, headers=browser).json() == {
                "received": True,
                "batch_count": 2,
            }
        open_cases = end_user.get("/alerts?view=my_cases&finding=investigating").text
        assert "CH-IMT-ATTRIBUTED" in open_cases and "CH-IMT-SAME-BATCH" in open_cases
        assert (
            "Update findings for this batch (2 alerts)"
            in end_user.get(f"/alerts/{attributed_id}").text
        )
        for _ in range(2):
            assert end_user.post(endpoint, json=bulk, headers=browser).json() == {
                "received": True,
                "batch_count": 2,
            }
        assert "Awaiting SMVS review" in end_user.get(f"/alerts/{sibling_id}").text
        assert end_user.get(f"/alerts/{unrelated_id}").status_code == 404
        assert (
            end_user.post(
                endpoint, json={**bulk, "submission_key": str(uuid4())}, headers=browser
            ).status_code
            == 409
        )
        assert "PRIVATE-SERIAL" not in listing
        assert end_user.get(f"/alerts/{foreign_id}").status_code == 404
        assert "Your investigation" not in end_user.get(f"/alerts/{other_id}").text
        page = end_user.get(f"/alerts/{identifier}")
        assert (
            "PRIVATE-SERIAL" in page.text
            and "PRIVATE INTERNAL MESSAGE" not in page.text
        )
        body = {
            "publication": identifier,
            "basis": version,
            "submission_key": str(uuid4()),
            "comparison": "no",
            "finding": "not_my_side",
            "pack_on_hold": True,
        }
        for _ in range(2):
            assert end_user.post(
                f"/alerts/{identifier}/findings", json=body, headers=browser
            ).json() == {"received": True}
        assert (
            end_user.post(
                f"/alerts/{foreign_id}/findings", json=body, headers=browser
            ).status_code
            == 404
        )
        ref = "CH-test-001"
        assert ref not in end_user.get("/alerts").text
        assert (
            ref
            in end_user.get(
                "/alerts?view=completed&finding=not_my_side&q=CH-test-001"
            ).text
        )
        assert "Keep pack on hold" in end_user.get("/alerts?view=on_hold").text
        assert "Keep pack on hold" in end_user.get(f"/alerts/{identifier}").text

        with browser_client() as priority_mah:
            assert (
                priority_mah.post(
                    "/alerts/access/challenge",
                    json={"token": sent["mah@example.test"]},
                    headers=browser,
                ).status_code
                == 200
            )
            assert (
                priority_mah.post(
                    "/alerts/access/verify",
                    json={"code": codes["mah@example.test"]},
                    headers=browser,
                ).status_code
                == 200
            )
            mah_cookie = priority_mah.cookies.get(ACCESS_COOKIE)
            mah_finding = {
                "publication": identifier,
                "basis": version,
                "submission_key": str(uuid4()),
                "batch_uploaded": "yes",
                "serial_accepted": "yes",
                "finding": "not_my_side",
            }
            assert (
                priority_mah.post(
                    f"/alerts/{identifier}/findings", json=mah_finding, headers=browser
                ).status_code
                == 200
            )
        assert ref in web.get(url + "/review", headers=nmvo).text
        unresolved = end_user.get(f"/alerts/{identifier}").text
        assert (
            "Cause unresolved" in unresolved
            and "Suspected falsification" not in unresolved
        )

        delivered = []
        monkeypatch.setattr(
            collaboration_routes.pilot_mail,
            "send_case_update",
            lambda address, reference, case_id: delivered.append(
                (address, reference, case_id)
            ),
        )
        update_url = f"/exceptions/{identifier}/invitations/case-update"
        decision = {
            "basis": version,
            "update_version": "",
            "pack_instruction": "suspected",
            "note": "Keep this pack separate and wait for further instructions.",
            "follow_up": "yes",
        }
        assert (
            web.post(
                update_url, data=decision, headers={**nmvo, "x-test-role": "mah"}
            ).status_code
            == 403
        )
        assert (
            web.post(
                update_url, data=decision, headers=nmvo, follow_redirects=False
            ).status_code
            == 303
        )
        assert delivered == [("alert@example.test", ref, identifier)]
        assert "Suspected falsification" in end_user.get("/alerts").text
        assert "SMVS requests an update" in end_user.get("/alerts").text
        assert "Suspected falsification" in end_user.get(f"/alerts/{identifier}").text
        assert web.post(update_url, data=decision, headers=nmvo).status_code == 409
        assert len(delivered) == 1
        assert (
            end_user.post(
                f"/alerts/{identifier}/findings",
                json={**body, "submission_key": str(uuid4())},
                headers=browser,
            ).status_code
            == 200
        )
        assert ref not in end_user.get("/alerts").text
        release = {
            **decision,
            "update_version": "1",
            "pack_instruction": "released",
            "follow_up": "",
            "concluded": "yes",
            "note": "Follow the verified local procedure.",
        }
        assert (
            web.post(
                update_url, data=release, headers=nmvo, follow_redirects=False
            ).status_code
            == 303
        )
        assert "Quarantine lifted" in end_user.get(f"/alerts/{identifier}").text
        assert ref not in end_user.get("/alerts?view=on_hold").text
        assert len(delivered) == 2
        assert ref not in web.get(url + "/review", headers=nmvo).text

        with factory() as session:
            grant = session.scalar(
                select(AlertDeskAccess).where(AlertDeskAccess.role == "end_user")
            )
            grant_id = grant.id
            assert session.scalar(select(func.count()).select_from(AlertDeskEvent)) == 7
        assert "Access confirmed" in web.get(url, headers=nmvo).text
        assert (
            web.post(
                f"{url}/{grant_id}/revoke",
                data={"action": "revoke"},
                headers=nmvo,
                follow_redirects=False,
            ).status_code
            == 303
        )
        assert end_user.get(f"/alerts/{identifier}").status_code == 404

    with factory.begin() as session:
        expired = session.get(AlertDeskAccess, grant_id)
        expired.revoked_at = None
        expired.session_expires_at = utcnow() - timedelta(seconds=1)
        assert expired.invite_expires_at > utcnow()
    assert "Session expired" in web.get(url, headers=nmvo).text
    previous_invite = sent["alert@example.test"]
    assert (
        "1 of 1 selected invitations accepted"
        in web.post(
            url + "/send",
            data={
                "selected": next(key for key in choices if key.startswith("end_user:"))
            },
            headers=nmvo,
        ).text
    )
    assert sent["alert@example.test"] != previous_invite

    with browser_client() as mah:
        mah.cookies.set(ACCESS_COOKIE, mah_cookie, path="/alerts")
        mah_list = mah.get("/alerts").text
        assert "CH-A52-OTHER-CASE" not in mah_list
        assert "portal-module-nav" in mah_list and "portal-table-panel" in mah_list
        assert mah.get("/alerts/portal.css").status_code == 200
        assert mah.get(f"/alerts/{other_id}").status_code == 404
        page = mah.get(f"/alerts/{identifier}")
        assert (
            "Was this batch uploaded?" in page.text
            and "Synthetic location" not in page.text
        )
        imt_page = mah.get(f"/alerts/{attributed_id}")
        assert "Your investigation" in imt_page.text
        assert "Was this batch uploaded?" not in imt_page.text
        assert "foreign-location" not in imt_page.text
        preview = web.get(
            f"/exceptions/{attributed_id}/invitations/preview?role=mah", headers=nmvo
        )
        assert preview.status_code == 200 and "Your investigation" in preview.text
        assert "Update findings for this batch (2 alerts)" in preview.text
        assert 'data-batch-revision=""' in preview.text
        unrelated_preview = web.get(
            f"/exceptions/{identifier}/invitations/preview?role=mah", headers=nmvo
        )
        assert unrelated_preview.status_code == 200
        assert "Update findings for this batch" not in unrelated_preview.text
        body = {
            "publication": attributed_id,
            "basis": version,
            "submission_key": str(uuid4()),
            "finding": "other",
            "capa": "planned",
        }
        assert (
            mah.post(
                f"/alerts/{attributed_id}/findings",
                json={**body, "batch_uploaded": "no"},
                headers=browser,
            ).status_code
            == 422
        )
        assert (
            mah.post(
                f"/alerts/{attributed_id}/findings",
                json={**body, "capa": None},
                headers=browser,
            ).status_code
            == 422
        )
        assert "Update findings for this batch (2 alerts)" in imt_page.text
        batch_revision = re.search(
            r'data-batch-revision="([^"]+)"', imt_page.text
        ).group(1)
        batch_endpoint = f"/alerts/{attributed_id}/findings"
        assert mah.post(
            batch_endpoint,
            json={**body, "batch_revision": batch_revision},
            headers=browser,
        ).json() == {"received": True, "batch_count": 2}
        assert "Awaiting SMVS review" in mah.get(f"/alerts/{sibling_id}").text
        assert (
            "Update findings for this batch"
            not in mah.get(f"/alerts/{attributed_id}").text
        )
        assert (
            mah.post(
                f"/alerts/{unrelated_id}/findings", json=body, headers=browser
            ).status_code
            == 409
        )
        with factory.begin() as session:
            session.scalar(
                select(CRMContact).where(CRMContact.airtable_id == "mah")
            ).archived_at = utcnow()
        assert mah.get(f"/alerts/{identifier}").status_code == 404


def test_a7_participant_evidence_shares_only_the_matching_operations_with_end_user():
    from app.domain.investigations.pilot import a7_evidence

    at = datetime(2026, 11, 4, 18, 30, 49, tzinfo=UTC)
    prechecks = {
        "repeat": {
            "report_id": 8,
            "previous": {
                "at": at,
                "operation": "Export",
                "location": "private-location",
            },
            "repeat": {
                "at": at,
                "operation": "Export",
                "actual": "Exported",
                "transaction_id": "private-id",
            },
        },
        "report_id": 8,
        "report_captured_at": at,
    }
    evidence, audit = a7_evidence(prechecks, "end_user")
    assert "same location" in evidence["summary"]
    assert [event["title"] for event in audit["events"]] == [
        "Active → Exported",
        "Repeat Export rejected · A7",
    ]
    assert "private-" not in json.dumps(audit)
    assert a7_evidence(prechecks, "mah")[1] is None
    assert a7_evidence({"repeat": None}, "end_user")[1] is None
