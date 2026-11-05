import csv
import io
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.db.models import AcquiredArtifact, ImportMutex, StagingRow
from app.domain.exceptions.mapping import MUTEX, publish_exceptions
from app.domain.models import PackAuditReport, PackAuditRequest
from app.domain.pack_audit import service
from app.domain.pack_audit.timeline import summarize
from app.integration.sources.nmvs.pack_audit.parsing import (
    HEADERS,
    parse_pack_audit,
    same_pack,
)
from tests.domain.test_mapping import sessions  # noqa: F401
from tests.integration.exceptions.test_exceptions import NS, acquire, alert, page

PARAMS = {
    "productCodeScheme": "GTIN",
    "productCode": "4006381333931",
    "serialNumber": "000SnA",
}


def event(name, tx, time, details="", code="", severity="INFO"):
    return dict(
        zip(
            HEADERS,
            [
                time,
                "Test",
                tx,
                code,
                name,
                name,
                "batch-1",
                "",
                details,
                "PROCESS",
                severity,
            ],
            strict=True,
        )
    )


def events():
    return [
        event(
            "PpdNewPackCreated",
            "one",
            "2026-10-01T10:00:00Z",
            "AttemptedOperation: CREATED; Market: EU;",
        ),
        event(
            "IntermarketSuccessfulPackStateChange",
            "two",
            "2026-10-02T10:00:00.100Z",
            "InitialState: Active; ActualState: Exported; Market: CH; Location: L-1;",
        ),
        event(
            "IntermarketFailedAlreadyInRequestedState",
            "three",
            "2026-10-02T11:00:00.200Z",
            "InitialState: Exported; ActualState: Exported; TargetState: Exported; AttemptedOperation: EXPORTED; AlertId: CH-test-001; Market: CH;",
            "A7",
            "IMPORTANT",
        ),
        event(
            "Alert",
            "three",
            "2026-10-02T11:00:00.500Z",
            "UniqueAlertId: CH-test-001; AlertEventSource: NMVO;",
        ),
    ]


def content(rows=None, *, serial="000SnA"):
    b = io.StringIO(newline="")
    w = csv.writer(b)
    w.writerow(
        [
            "Report Type",
            "Report Name",
            "Product Code Scheme",
            "Product Code",
            "Pack Serial Number",
        ]
    )
    w.writerow(
        ["Pack Audit Trail Report", "Test", "GTIN", PARAMS["productCode"], serial]
    )
    w.writerow([])
    w.writerow(HEADERS)
    for r in events() if rows is None else rows:
        w.writerow([r[h] for h in HEADERS])
    return b.getvalue().encode()


@pytest.fixture
def factory(sessions):  # noqa: F811 - shared guarded fixture
    with sessions() as s:
        for name in (service.QUEUE_LOCK, service.WORKER_LOCK, MUTEX):
            s.add(ImportMutex(import_key=name))
        s.commit()
    publish_exceptions(sessions, acquire(sessions, [page([alert()])]), NS)
    return sessions


def test_source_parsing_and_transaction_grouping_do_not_multiply_alerts():
    parsed = parse_pack_audit(content())
    assert same_pack(parsed.file_metadata, PARAMS)
    assert not same_pack(parsed.file_metadata, {**PARAMS, "serialNumber": "000sna"})
    a = summarize(parsed.datasets[0].rows, alert_id="CH-test-001")
    assert (
        a["event_count"] == 4 and a["transaction_count"] == 3 and a["match_count"] == 1
    )
    assert [g["kind"] for g in a["groups"]] == ["created", "change", "error"]
    assert len(a["selected"]["items"]) == 2 and a["selected"]["actual"] == "Exported"
    assert (
        a["last_change"]["before"] == "Active"
        and a["last_change"]["actual"] == "Exported"
    )
    assert a["groups"][0]["actual"] is None  # Creation never invents an Active state.


def test_missing_time_unknown_events_and_conflicting_details_remain_visible():
    rows = [
        event("Unknown", "", "bad date", "ActualState: Active; ActualState: Exported;"),
        event("Unknown", "", "", ""),
    ]
    a = summarize(rows)
    assert (
        a["unknown_times"] == 2
        and a["transaction_count"] == 2
        and len(a["groups"]) == 2
    )
    assert a["groups"][0]["actual"] is None
    assert len(a["relevant"]) == 0
    assert not same_pack(
        parse_pack_audit(content()).file_metadata, {**PARAMS, "productCode": "wrong"}
    )


def test_queue_duplicate_clicks_and_same_pack_share_one_task(factory):
    first = service.request_report(factory, 1)
    second = service.request_report(factory, 1)
    assert first.id == second.id
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(PackAuditRequest)) == 1


def test_worker_reuses_successful_report_until_explicit_refresh(factory, monkeypatch):
    calls = []

    class Client:
        def get_pack(self, parameters, **kwargs):
            calls.append(parameters)
            return SimpleNamespace(
                content=content(),
                report_uri="https://example.test/report/reports/one",
                report_metadata={"request": parameters},
            )

        def close(self):
            pass

    monkeypatch.setattr(service, "reporting_client", lambda _: Client())
    task = service.request_report(factory, 1)
    assert service.tick(factory) == task.id
    assert service.tick(factory) is None
    reused = service.request_report(factory, 1)
    assert reused.status == "ready" and len(calls) == 1
    with factory() as s:
        before = s.scalar(select(func.count()).select_from(StagingRow))
        assert s.scalar(select(func.count()).select_from(PackAuditReport)) == 1
    refresh = service.request_report(factory, 1, refresh=True)
    assert refresh.status == "queued"
    service.tick(factory)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(PackAuditReport)) == 1
        assert s.scalar(select(func.count()).select_from(StagingRow)) == before
    assert len(calls) == 2


def test_wrong_pack_report_retained_and_not_published(factory, monkeypatch):
    class Client:
        def get_pack(self, parameters, **kwargs):
            return SimpleNamespace(
                content=content(serial="wrong"),
                report_uri="https://example.test/report/reports/wrong",
                report_metadata={"request": parameters},
            )

        def close(self):
            pass

    monkeypatch.setattr(service, "reporting_client", lambda _: Client())
    service.request_report(factory, 1)
    service.tick(factory)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(PackAuditReport)) == 0
        assert s.scalar(select(PackAuditRequest.status)) == "queued"
        assert s.scalar(select(PackAuditRequest.retry_at)) is not None
        assert s.scalar(
            select(AcquiredArtifact).where(
                AcquiredArtifact.report_type == "PackAuditTrailReport"
            )
        ).artifact_bytes == content(serial="wrong")


def test_informational_code_is_not_classified_as_failed_attempt():
    a = summarize([event("Info", "tx", "2026-10-02T10:00:00Z", code="15100000")])
    assert a["groups"][0]["kind"] == "other"


def test_numeric_operation_codes_do_not_hide_explicit_alert_codes_in_delivery_events():
    rows = [
        event(
            "PackStateTransitionFailedState",
            "tx",
            "2026-10-02T10:00:00Z",
            "InitialState: Supplied; ActualState: Supplied;",
            "51220200",
            "IMPORTANT",
        ),
        event(
            "Alert",
            "tx",
            "2026-10-02T10:00:00.100Z",
            "AlertCode: A7; AlertEventSource: NMVO;",
        ),
    ]
    a = summarize(rows)
    assert a["groups"][0]["kind"] == "error" and a["groups"][0]["codes"] == ["A7"]
