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
