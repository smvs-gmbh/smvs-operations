from types import SimpleNamespace

from app.domain.investigations.prechecks import identifier_checks, report_plan


def source(**overrides):
    return SimpleNamespace(
        **{
            "provided_batch": "00123456",
            "stored_batch": "00123456",
            "serial_number": "00123456789012",
            "error_code": "A3",
            "is_intermarket": 0,
            "source_market": "CH",
            **overrides,
        }
    )


def constraints(**overrides):
    return SimpleNamespace(
        evidence={
            "Min SN Length": "14",
            "Max SN Length": "14",
            "SN Format": "N",
            "Batch Length": "8",
            **overrides,
        }
    )


def results(checks):
    return {c["code"]: c["result"] for c in checks}


def test_length_preserves_identifiers_and_does_not_confirm_authenticity():
    record = source()
    checks = identifier_checks(record, {"provided_batch": constraints()})
    assert results(checks)["serial-length"] == "consistent"
    assert results(checks)["batch-comparison"] == "consistent"
    assert results(checks)["format"] == "unknown"
    assert "does not confirm" in next(
        c["detail"] for c in checks if c["code"] == "serial-length"
    )
    assert record.serial_number == "00123456789012"
    assert report_plan(record, checks)["action"] == "request"


def test_wrong_length_routes_to_pack_comparison_instead_of_wasted_report():
    record = source(serial_number="01234")
    checks = identifier_checks(record, {"provided_batch": constraints()})
    assert results(checks)["serial-length"] == "discrepancy"
    assert report_plan(record, checks)["action"] == "compare"


def test_different_stored_batch_constraints_are_never_substituted():
    record = source(
        provided_batch="UNKNOWN", stored_batch="00123456", serial_number="ABC"
    )
    checks = identifier_checks(record, {"stored_batch": constraints()})
    assert results(checks)["batch-comparison"] == "discrepancy"
    assert results(checks)["snapshot-batch"] == "unknown"
    assert results(checks)["serial-length"] == "unknown"
    assert "never uploaded" in next(
        c["detail"] for c in checks if c["code"] == "snapshot-batch"
    )


def test_bad_or_missing_constraints_stay_unknown():
    for lo, hi in [
        ("14", "2"),
        ("", "14"),
        ("0", "14"),
        ("14.5", "20"),
        ("-1", "20"),
        ("999", "999"),
    ]:
        checks = identifier_checks(
            source(),
            {
                "provided_batch": constraints(
                    **{"Min SN Length": lo, "Max SN Length": hi}
                )
            },
        )
        assert results(checks)["serial-length"] == "unknown"
    assert (
        results(identifier_checks(source(serial_number=None), {}))["serial-length"]
        == "unknown"
    )


def test_report_planning_is_bounded_to_local_supported_relevant_cases():
    assert report_plan(source(error_code="A2"), [])["action"] == "uploads"
    for record in [
        source(is_intermarket=1),
        source(is_intermarket=None),
        source(source_market="DE"),
        source(error_code="unknown"),
    ]:
        assert report_plan(record, [])["action"] == "review"
    assert report_plan(source(), [], supported=False)["action"] == "review"
    assert (
        report_plan(source(is_intermarket=1), [], report=object())["action"] == "reuse"
    )
    assert (
        report_plan(source(), [], task=SimpleNamespace(status="queued"))["action"]
        == "pending"
    )
