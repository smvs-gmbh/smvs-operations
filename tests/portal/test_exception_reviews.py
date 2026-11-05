import re

import pytest
from sqlalchemy import func, select

from app.domain.exceptions.mapping import publish_exceptions
from app.domain.models import ExceptionReview, ExceptionReviewEvent, NMVSException
from tests.integration.exceptions.test_exceptions import NS, acquire, alert, page

BASE = "/exceptions?start=2026-10-01&end=2026-10-31"
ORIGIN = {"origin": "http://testserver"}


def seed(factory, rows=None):
    publish_exceptions(factory, acquire(factory, [page(rows or [alert()])]), NS)


def version(client, identifier=1):
    return re.search(
        r'name="version" value="([^"]+)"',
        client.get(f"/exceptions/{identifier}/analysis").text,
    )[1]


def save(client, identifier=1, **values):
    data = {
        "version": version(client, identifier),
        "status": "open",
        "command": "save",
        "cause": "",
        "findings": "",
        "next_action": "",
        "review_reason": "",
        "due_date": "",
    }
    data.update(values)
    if data.get("status") == "reviewed":
        data.update(
            command="resolve",
            resolution_basis="no_further_action",
            complete_pending="yes",
        )
        data.pop("status")
    return client.post(
        f"/exceptions/{identifier}/review",
        data=data,
        headers=ORIGIN,
        follow_redirects=False,
    )


def test_review_is_local_reversible_and_audited(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    with factory() as s:
        original = s.get(NMVSException, 1).payload_hash
    assert (
        save(
            client, status="reviewed", review_reason="No local follow-up required"
        ).status_code
        == 303
    )
    assert ">CH-test-001</a>" not in client.get(BASE).text
    assert ">CH-test-001</a>" in client.get(BASE + "&work_status=resolved").text
    assert ">CH-test-001</a>" in client.get(BASE + "&work_status=all").text
    assert (
        client.post(
            "/exceptions/1/review",
            data={
                "version": version(client),
                "command": "reopen",
                "reopen_reason": "Additional checks required",
            },
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert ">CH-test-001</a>" in client.get(BASE).text
    with factory() as s:
        assert s.get(NMVSException, 1).payload_hash == original
        assert s.scalar(select(func.count()).select_from(ExceptionReviewEvent)) == 2
        assert s.get(ExceptionReview, 1).status == "open"


def test_to_do_keeps_older_items_and_follow_up(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    assert (
        save(
            client,
            status="to_do",
            next_action="Check scanner settings",
            due_date="2026-11-10",
        ).status_code
        == 303
    )
    text = client.get(
        "/exceptions?start=2026-11-01&end=2026-11-30&work_status=to_do"
    ).text
    assert (
        ">CH-test-001</a>" in text
        and "Check scanner settings" in text
        and "2026-11-10" in text
    )
    assert "source date filter not applied" in text


def test_stale_review_and_changed_source_are_detected(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    old = version(client)
    assert save(client, status="reviewed", review_reason="Reviewed").status_code == 303
    assert (
        client.post(
            "/exceptions/1/review",
            data={"version": old, "status": "open", "command": "save"},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    with factory() as s:
        record = s.get(NMVSException, 1)
        record.payload_hash = "f" * 64
        s.commit()
    assert ">CH-test-001</a>" in client.get(BASE).text
    assert "Needs review" in client.get(BASE).text
    assert "Source data changed" in client.get("/exceptions/1/analysis").text
    assert ">CH-test-001</a>" not in client.get(BASE + "&work_status=resolved").text


@pytest.mark.parametrize(
    "data",
    [
        {"status": "reviewed"},
        {"status": "to_do"},
        {"status": "invalid"},
        {"status": "open", "due_date": "2026-99-99"},
        {"status": "open", "cause": "x" * 4001},
    ],
)
def test_invalid_forms_do_not_create_reviews(exceptions_portal, data):
    client, factory = exceptions_portal
    seed(factory)
    assert save(client, **data).status_code == 422
    with factory() as s:
        assert s.get(ExceptionReview, 1) is None


def test_origin_and_escaped_content(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    assert (
        client.post("/exceptions/1/review", data={"status": "open"}).status_code == 403
    )
    assert (
        client.post(
            "/exceptions/1/review",
            data={"status": "open"},
            headers={"origin": "https://evil.test"},
        ).status_code
        == 403
    )
    assert save(client, cause="<script>unsafe</script>").status_code == 303
    assert (
        "&lt;script&gt;unsafe&lt;/script&gt;"
        in client.get("/exceptions/1/analysis").text
    )


def test_bulk_preview_exact_scope_explicit_selection_and_history(exceptions_portal):
    client, factory = exceptions_portal
    seed(
        factory,
        [
            alert("SOURCE"),
            alert("MATCH", serialNumber="another"),
            alert("CASE", providedBatchNumber="bad"),
            alert("MARKET", sourceMarket="DE"),
            alert("UNSELECTED", serialNumber="third"),
        ],
    )
    assert (
        save(
            client,
            cause="Scanner configuration error",
            review_reason="Confirmed locally",
            command="resolve",
            resolution_basis="confirmed_cause",
            category="data_capture",
            confidence="confirmed",
            findings="Raw scan and physical pack compared; scanner adds a character.",
            check_data_capture_pack="checked",
            check_data_capture_input="checked",
        ).status_code
        == 303
    )
    text = client.get("/exceptions/1/similar").text
    assert "target_2" in text and "target_5" in text
    assert "target_3" not in text and "target_4" not in text
    data = {
        "version": version(client),
        "target_2": version(client, 2),
        "command": "resolve_similar",
        "reason": "Same scanner and confirmed settings",
    }
    assert (
        client.post(
            "/exceptions/1/similar", data=data, headers=ORIGIN, follow_redirects=False
        ).status_code
        == 303
    )
    with factory() as s:
        assert s.get(ExceptionReview, 2).status == "resolved"
        assert s.get(ExceptionReview, 2).cause == "Scanner configuration error"
        assert s.get(ExceptionReview, 5) is None
        event = s.scalar(
            select(ExceptionReviewEvent).where(ExceptionReviewEvent.exception_id == 2)
        )
        assert event.originating_exception_id == 1
    # An unrelated ID cannot be injected into the form.
    data.update(target_3=version(client, 3))
    assert (
        client.post("/exceptions/1/similar", data=data, headers=ORIGIN).status_code
        == 409
    )


def test_bulk_does_not_overwrite_to_do_or_partially_save(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory, [alert("SOURCE"), alert("MATCH"), alert("TODO")])
    save(
        client,
        cause="Root cause",
        review_reason="Evidence checked",
        command="resolve",
        resolution_basis="confirmed_cause",
        category="other",
        confidence="confirmed",
        findings="Alternative cause supported by evidence",
        check_other_description="checked",
        check_other_evidence="checked",
    )
    save(client, 3, status="to_do", next_action="Waiting for evidence")
    data = {
        "version": version(client),
        "target_2": version(client, 2),
        "command": "resolve_similar",
        "target_3": version(client, 3),
        "reason": "Same cause",
    }
    assert (
        client.post("/exceptions/1/similar", data=data, headers=ORIGIN).status_code
        == 409
    )
    with factory() as s:
        assert s.get(ExceptionReview, 2) is None
        assert s.get(ExceptionReview, 3).status == "to_do"


def test_repeat_identical_save_does_not_add_history(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    save(client, cause="A finding")
    save(client, cause="A finding")
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(ExceptionReviewEvent)) == 1


def test_analysis_is_a_separate_tab_and_legacy_text_is_preserved(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    assert save(client, cause="Earlier free-text finding").status_code == 303
    context = client.get("/exceptions/1").text
    assert 'href="/exceptions/1/analysis?nav_start=' in context
    assert 'name="cause"' not in context
    analysis = client.get("/exceptions/1/analysis").text
    assert "Earlier free-text finding" in analysis
    assert "not been classified or automatically confirmed" in analysis
    assert "Classify the cause" in analysis and "Check the evidence" in analysis
    assert "Record the assessment" in analysis and "Decide the next step" in analysis
    assert (
        client.get("/exceptions/1/source").text.count(
            'href="/exceptions/1/analysis?nav_start='
        )
        == 1
    )
    assert client.get("/exceptions/999/analysis").status_code == 404


def test_structured_assessment_is_saved_and_audited(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    response = save(
        client,
        category="repeat_operation",
        confidence="confirmed",
        cause="Retry after successful destruction",
        findings="Two operations in audit history",
        check_repeat_operation_previous="checked",
        check_repeat_operation_repeat="checked",
    )
    assert (
        response.status_code == 303
        and "/analysis?notice=saved" in response.headers["location"]
    )
    with factory() as session:
        review = session.get(ExceptionReview, 1)
        assert review.analysis["category"] == "repeat_operation"
        assert review.analysis["confidence"] == "confirmed"
        event = session.scalar(select(ExceptionReviewEvent))
        assert event.after["analysis"] == review.analysis
    text = client.get("/exceptions/1/analysis").text
    assert '<option value="repeat_operation" selected>' in text
    assert '<option value="confirmed" selected>' in text


@pytest.mark.parametrize(
    "values",
    [
        {"category": "invalid", "confidence": "suspected"},
        {"category": "unknown", "confidence": "confirmed"},
        {"category": "technical", "confidence": "certain"},
        {
            "category": "technical",
            "confidence": "suspected",
            "check_technical_logs": "invalid",
        },
        {
            "category": "technical",
            "confidence": "confirmed",
            "cause": "X",
            "findings": "Some evidence",
        },
        {
            "category": "technical",
            "confidence": "confirmed",
            "cause": "X",
            "findings": "",
            "check_technical_logs": "checked",
            "check_technical_incident": "checked",
        },
        {
            "category": "technical",
            "confidence": "confirmed",
            "cause": "X",
            "findings": "Some evidence",
            "check_technical_logs": "not_applicable",
            "check_technical_incident": "not_applicable",
        },
    ],
)
def test_structured_validation_prevents_false_confirmation(exceptions_portal, values):
    client, factory = exceptions_portal
    seed(factory)
    assert save(client, **values).status_code == 422
    with factory() as session:
        assert session.get(ExceptionReview, 1) is None


def test_hypothesis_cannot_be_applied_as_shared_root_cause(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory, [alert("SOURCE"), alert("MATCH")])
    assert (
        save(
            client,
            category="upload",
            confidence="suspected",
            cause="Possibly late upload",
            review_reason="Check required",
        ).status_code
        == 303
    )
    data = {
        "version": version(client),
        "target_2": version(client, 2),
        "command": "resolve_similar",
        "reason": "Seems similar",
    }
    assert (
        client.post("/exceptions/1/similar", data=data, headers=ORIGIN).status_code
        == 422
    )
    with factory() as session:
        assert session.get(ExceptionReview, 2) is None


def test_save_cannot_resolve_and_resolve_requires_explicit_basis(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    token = version(client)
    base = {
        "version": token,
        "status": "resolved",
        "command": "save",
        "review_reason": "Checked",
    }
    assert (
        client.post("/exceptions/1/review", data=base, headers=ORIGIN).status_code
        == 422
    )
    base.update(command="resolve", resolution_basis="confirmed_cause")
    assert (
        client.post("/exceptions/1/review", data=base, headers=ORIGIN).status_code
        == 422
    )
    base.update(resolution_basis="no_further_action", review_reason="")
    assert (
        client.post("/exceptions/1/review", data=base, headers=ORIGIN).status_code
        == 422
    )
    with factory() as session:
        assert session.get(ExceptionReview, 1) is None


def test_resolution_reopen_history_and_locked_resolved_analysis(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    assert (
        save(
            client,
            command="resolve",
            resolution_basis="no_further_action",
            review_reason="Other NMVO is responsible",
        ).status_code
        == 303
    )
    text = client.get("/exceptions/1/analysis").text
    assert "Reopen exception" in text and 'analysis-edit-fields" disabled' in text
    assert save(client, cause="Silent change").status_code == 409
    assert (
        client.post(
            "/exceptions/1/review",
            data={"version": version(client), "command": "reopen", "reopen_reason": ""},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/exceptions/1/review",
            data={
                "version": version(client),
                "command": "reopen",
                "reopen_reason": "New evidence received",
            },
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    with factory() as session:
        record = session.get(ExceptionReview, 1)
        assert record.status == "open"
        events = session.scalars(
            select(ExceptionReviewEvent).order_by(ExceptionReviewEvent.id)
        ).all()
        assert events[0].after["resolution"]["basis"] == "no_further_action"
        assert (
            events[1].after["resolution"]["reopened_reason"] == "New evidence received"
        )


def test_resolve_requires_acknowledgement_of_previous_follow_up(exceptions_portal):
    client, factory = exceptions_portal
    seed(factory)
    save(client, next_action="Obtain scanner logs", due_date="2026-11-10")
    # Clearing the form must not bypass the pending-work safeguard.
    assert (
        save(
            client,
            command="resolve",
            resolution_basis="no_further_action",
            review_reason="No further local action",
        ).status_code
        == 422
    )
    assert (
        save(
            client,
            command="resolve",
            resolution_basis="no_further_action",
            review_reason="Logs reviewed; no further local action",
            complete_pending="yes",
        ).status_code
        == 303
    )


def test_shared_resolution_requires_resolved_origin_and_protects_open_follow_up(
    exceptions_portal,
):
    client, factory = exceptions_portal
    seed(factory, [alert("SOURCE"), alert("TARGET")])
    confirmed = {
        "category": "technical",
        "confidence": "confirmed",
        "cause": "Interface retry defect",
        "findings": "Verified request logs and incident reference",
        "check_technical_logs": "checked",
        "check_technical_incident": "checked",
        "review_reason": "Defect confirmed",
    }
    save(client, **confirmed)
    data = {
        "version": version(client),
        "target_2": version(client, 2),
        "command": "resolve_similar",
        "reason": "Same incident and request pattern",
    }
    assert (
        client.post("/exceptions/1/similar", data=data, headers=ORIGIN).status_code
        == 422
    )
    save(client, command="resolve", resolution_basis="confirmed_cause", **confirmed)
    save(client, 2, next_action="Local check still pending")
    data.update(version=version(client), target_2=version(client, 2))
    assert (
        client.post("/exceptions/1/similar", data=data, headers=ORIGIN).status_code
        == 409
    )
    with factory() as session:
        assert session.get(ExceptionReview, 2).status == "open"


def test_reopen_selected_batch_is_atomic_and_audited(exceptions_portal):
    client, factory = exceptions_portal
    seed(
        factory,
        [alert("CASE-1"), alert("CASE-2"), alert("OTHER", storedBatchNumber="Other")],
    )
    for identifier in (1, 2, 3):
        assert (
            save(
                client, identifier, status="reviewed", review_reason="Test resolution"
            ).status_code
            == 303
        )
    url = "/exceptions/1/reopen-batch"
    preview = client.get(url).text
    assert "CASE-1" in preview and "CASE-2" in preview and "OTHER" not in preview
    data = {
        "target_1": version(client),
        "target_2": version(client, 2),
        "reason": "Undo test resolutions",
    }
    assert client.post(url, data=data).status_code == 403
    assert (
        client.post(
            url, data={**data, "target_3": version(client, 3)}, headers=ORIGIN
        ).status_code
        == 409
    )
    assert "CASE-1" not in client.get(BASE).text
    assert (
        client.post(
            url, data={**data, "target_2": "0:" + "0" * 64}, headers=ORIGIN
        ).status_code
        == 409
    )
    assert "CASE-1" not in client.get(BASE).text
    assert (
        client.post(url, data=data, headers=ORIGIN, follow_redirects=False).status_code
        == 303
    )
    listing = client.get(BASE).text
    assert "CASE-1" in listing and "CASE-2" in listing and "OTHER" not in listing
    with factory() as session:
        reopened = session.scalars(
            select(ExceptionReviewEvent)
            .order_by(ExceptionReviewEvent.id.desc())
            .limit(2)
        ).all()
        assert {event.exception_id for event in reopened} == {1, 2}
        assert all(
            event.before["status"] == "resolved" and event.after["status"] == "open"
            for event in reopened
        )
        assert all(
            event.after["resolution"]["reopened_reason"] == data["reason"]
            for event in reopened
        )


@pytest.mark.parametrize("repeat_location", ["L-1", "L-2"])
@pytest.mark.parametrize("operation", ["Export", "Destroy"])
def test_repeat_short_resolution_requires_matching_audit_location(
    exceptions_portal, repeat_location, operation
):
    from app.core.db.models import ImportMutex
    from app.domain.models import PackAuditRequest
    from app.domain.pack_audit import service
    from tests.integration.pack_audit.test_pack_audit import PARAMS, content, events

    client, factory = exceptions_portal
    common = {
        "errorCode": "A7",
        "attemptedOperation": "EXPORTED" if operation == "Export" else "DESTROYED",
        "sourceLocationID": "L-1",
    }
    seed(
        factory,
        [
            alert(transactionID="three", **common),
            alert("CH-test-002", serialNumber="other-serial", **common),
            alert("CH-test-003", serialNumber="pending-serial", **common),
            alert(
                "CH-test-004",
                serialNumber="different-location",
                **{**common, "sourceLocationID": "L-2"},
            ),
        ],
    )
    rows = events()
    rows[1]["Event Details"] += " AttemptedOperation: EXPORTED;"
    rows[2]["Event Details"] += f" Location: {repeat_location};"
    if operation == "Destroy":
        for row in rows:
            row["Event Details"] = (
                row["Event Details"]
                .replace("Exported", "Destroyed")
                .replace("EXPORTED", "DESTROYED")
            )
    with factory() as session:
        session.add(ImportMutex(import_key=service.QUEUE_LOCK))
        run = service.retain(
            session,
            content(rows=rows),
            "https://example.test/report/reports/one",
            {"request": PARAMS},
        )
        report_id = service.publish(session, run, NS, PARAMS).id
        session.commit()
    task = service.request_report(factory, 1)
    with factory() as session:
        request = session.get(PackAuditRequest, task.id)
        request.latest_report_id = report_id
        request.status = "ready"
        session.commit()
    analysis = client.get("/exceptions/1/analysis").text
    assert "Intelligence · Automatic analysis" in analysis
    assert f"Repeated {operation} evidence" in analysis
    eligible = repeat_location == "L-1"
    assert ("Resolve locally" in analysis) == eligible
    response = client.post(
        "/exceptions/1/resolve-repeat",
        headers=ORIGIN,
        follow_redirects=False,
        data={
            "version": version(client),
            "report_id": report_id,
            "reason": "Same-location repeat",
        },
    )
    assert response.status_code == (303 if eligible else 409)
    with factory() as session:
        review = session.get(ExceptionReview, 1)
        if eligible:
            assert review.status == "resolved"
            assert review.resolution["pack_audit_report_id"] == report_id
            assert review.resolution["earlier_transaction_id"] == "two"
            assert review.resolution["repeat_transaction_id"] == "three"
        else:
            assert review is None

    batch_url = "/exceptions/1/resolve-export-batch"
    if operation == "Destroy":
        assert "/resolve-export-batch" not in analysis
        return
    if not eligible:
        assert client.get(batch_url).status_code == 409
        return
    preview = client.get(batch_url).text
    assert "2 eligible exceptions" in preview
    old_fingerprint = re.search(r'name="fingerprint" value="([^"]+)"', preview)[1]
    assert (
        save(client, 3, status="to_do", next_action="Check scanner").status_code == 303
    )
    assert (
        client.post(
            batch_url,
            headers=ORIGIN,
            data={"fingerprint": old_fingerprint, "reason": "Repeat"},
        ).status_code
        == 409
    )
    preview = client.get(batch_url).text
    assert "1 eligible exception" in preview and "CH-test-004" not in preview
    fingerprint = re.search(r'name="fingerprint" value="([^"]+)"', preview)[1]
    assert (
        client.post(
            batch_url,
            headers=ORIGIN,
            data={"fingerprint": fingerprint, "reason": "Repeat"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    with factory() as session:
        other = session.get(ExceptionReview, 2)
        assert other.status == "resolved"
        assert other.resolution["pack_audit_scope"] == "originating_pack_only"
        assert session.get(ExceptionReview, 3).status == "to_do"
        assert session.get(ExceptionReview, 4) is None
    resolved = client.get(BASE + "&work_status=resolved").text
    assert 'name="target_1"' in resolved and 'name="target_2"' in resolved
    response = client.post(
        "/exceptions/reopen-selected?start=2026-10-01&end=2026-10-31&work_status=resolved",
        headers=ORIGIN,
        data={
            "target_1": version(client),
            "target_2": version(client, 2),
            "reason": "Undo test",
        },
    )
    assert (
        response.status_code == 200 and "Selected exceptions reopened." in response.text
    )
    assert "CH-test-001" in response.text and "CH-test-002" in response.text
    with factory() as session:
        assert (
            session.get(ExceptionReview, 1).status
            == session.get(ExceptionReview, 2).status
            == "open"
        )

    # Apply the rule after reopening. Each selected pack requires its own proof.
    from app.portal.intelligence_routes import router as intelligence_router

    client.app.include_router(intelligence_router)
    selected = {"target_1": version(client), "target_2": version(client, 2)}
    assert (
        client.post(
            "/intelligence/rules",
            headers=ORIGIN,
            data={
                "version": "1",
                "operation": "EXPORTED",
                "market": "CH",
            },
            follow_redirects=False,
        ).status_code
        == 303
    )
    rule_preview = client.get(
        "/intelligence/rules?preview=true&start=2026-10-01&end=2026-10-31"
    )
    assert rule_preview.status_code == 200 and "Scope version 2" in rule_preview.text
    preview = client.post("/intelligence/apply", headers=ORIGIN, data=selected)
    assert preview.status_code == 200 and "1 of 2 selected exceptions" in preview.text
    fingerprint = re.search(r'name="fingerprint" value="([^"]+)"', preview.text)[1]
    with factory() as session:
        assert session.get(ExceptionReview, 1).status == "open"
    action = client.post(
        "/intelligence/apply",
        headers=ORIGIN,
        data={
            **selected,
            "confirm": "yes",
            "fingerprint": fingerprint,
            "reason": "Audit evidence checked",
        },
        follow_redirects=False,
    )
    assert action.status_code == 303
    with factory() as session:
        assert session.get(ExceptionReview, 1).resolution["rule_version"] == 2
        assert session.get(ExceptionReview, 2).status == "open"


def test_work_audit_displays_resolution_and_reopen_for_this_exception(
    exceptions_portal,
):
    client, factory = exceptions_portal
    seed(factory, [alert("CASE-1"), alert("CASE-2")])
    assert (
        save(
            client, status="reviewed", review_reason="Same-location repeat"
        ).status_code
        == 303
    )
    assert (
        save(
            client, 2, status="reviewed", review_reason="Other case reason"
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/exceptions/1/review",
            headers=ORIGIN,
            follow_redirects=False,
            data={
                "command": "reopen",
                "version": version(client),
                "reopen_reason": "Recheck evidence",
            },
        ).status_code
        == 303
    )
    response = client.get("/exceptions/1/work-audit")
    assert response.status_code == 200
    assert "Resolved locally" in response.text and "Reopened" in response.text
    assert (
        "Same-location repeat" in response.text and "Recheck evidence" in response.text
    )
    assert "Before and after" in response.text
    assert "Local operator (no authenticated identity)" in response.text
    assert "Other case reason" not in response.text
    assert client.get("/exceptions/999/work-audit").status_code == 404
