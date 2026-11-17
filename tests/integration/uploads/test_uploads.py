import csv
import io
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.db.models import AcquiredArtifact, ImportMutex, StagingRow
from app.domain.models import UploadReport, UploadRequest
from app.domain.uploads import service
from app.integration.failures import IntegrationExecutionError
from app.integration.sources.nmvs.uploads.parsing import HEADERS, parse_upload
from app.portal.upload_routes import evidence
from tests.domain.test_mapping import sessions  # noqa: F401

NS = "nmvs-origin:https://example.test"
START, END = datetime.fromisoformat("2026-10-01"), datetime.fromisoformat("2026-10-03")


def content(
    *, filter_name="Genuine Transactions", rows=None, end="2026-10-03T00:00:00Z"
):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Report Type",
            "Report Name",
            "Start Date & Time (UTC)",
            "End Date & Time (UTC)",
            "Synthetic Monitoring",
        ]
    )
    writer.writerow(
        [
            "Product Pack Upload Audit Trail Report",
            "Upload test",
            "2026-10-01T00:00:00Z",
            end,
            filter_name,
        ]
    )
    writer.writerow([])
    writer.writerow(HEADERS)
    for row in (
        rows
        if rows is not None
        else [
            [
                "2026-10-02T11:00:00Z",
                "ProcessedSuccessfulPpdCreateMessage",
                "PPD message processed",
                "tx-1",
                "GTIN",
                "04006381333931",
                "PPD",
                "BatchId: Lot-001;\\r\\nNumberOfPacksInRequest: 20; NumberOfPacksSuccessfullyUploaded: 18; NumberOfUnsuccessfulPackUploads: 2;",
                "PROCESS",
                "IMPORTANT",
            ]
        ]
    ):
        writer.writerow(row)
    return buffer.getvalue().encode()


def record(**kwargs):
    return SimpleNamespace(
        source_namespace=kwargs.get("namespace", NS),
        product_code_scheme="GTIN",
        product_code="4006381333931",
        provided_batch=kwargs.get("batch", "Lot-001"),
        stored_batch=None,
        alert_at=datetime.fromisoformat("2026-10-02T10:00:00"),
    )


@pytest.fixture
def factory(sessions):  # noqa: F811
    with sessions() as s:
        s.add_all(
            [
                ImportMutex(import_key=service.QUEUE_LOCK),
                ImportMutex(import_key=service.WORKER_LOCK),
            ]
        )
        s.commit()
    return sessions


def retain(factory, data=None, *, namespace=NS):
    with factory() as s:
        run_id = service.retain(
            s,
            data or content(),
            None,
            {
                "source_namespace": namespace,
                "request": {
                    "startDateTime": "2026-10-01T00:00:00Z",
                    "endDateTime": "2026-10-03T00:00:00Z",
                    "syntheticMonitoring": False,
                },
            },
            provided=True,
        )
        report = service.publish(s, run_id, namespace)
        s.commit()
        return report.id


@pytest.mark.parametrize(
    "filter_name", ["All Transactions", "Synthetic Transactions", ""]
)
def test_rejects_unconfirmed_genuine_filter(filter_name):
    with pytest.raises(ValueError, match="filter"):
        parse_upload(content(filter_name=filter_name))


def test_empty_report_proves_coverage_and_rejects_out_of_window_event():
    assert not parse_upload(content(rows=[])).datasets[0].rows
    with pytest.raises(ValueError, match="outside"):
        parse_upload(content(end="2026-10-02T00:00:00Z"))


def test_exact_replay_reuses_staging_and_report(factory):
    first = retain(factory)
    with factory() as s:
        count = s.scalar(select(func.count()).select_from(StagingRow))
    assert retain(factory) == first
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(StagingRow)) == count
        assert s.scalar(select(func.count()).select_from(UploadReport)) == 1
        result = evidence(s, record(), START, END)
        assert result["covered"] and result["rows"][0]["after_alert"]
        assert (
            result["rows"][0]["successful"] == "18"
            and result["rows"][0]["unsuccessful"] == "2"
        )
        assert not evidence(s, record(batch="LOT-001"), START, END)["rows"]
        assert not evidence(s, record(namespace="other"), START, END)["covered"]


def test_overlapping_versions_do_not_duplicate_visible_events(factory):
    retain(factory)
    retain(factory, content().replace(b"Upload test", b"Upload another request"))
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(UploadReport)) == 2
        assert len(evidence(s, record(), START, END)["rows"]) == 1


def test_partial_coverage_is_not_negative_evidence(factory):
    retain(factory)
    with factory() as s:
        result = evidence(s, record(batch="missing"), START - timedelta(days=1), END)
        assert not result["covered"] and not result["rows"]
    assert service.covered(
        [SimpleNamespace(period_start=START, period_end=END)], START, END
    )
    assert not service.covered(
        [
            SimpleNamespace(period_start=START, period_end=START + timedelta(days=1)),
            SimpleNamespace(period_start=END, period_end=END + timedelta(days=1)),
        ],
        START,
        END,
    )


def test_queue_reuses_across_product_and_refresh_retains_old_evidence(
    factory, monkeypatch
):
    first = service.request_report(factory, NS, START, END)
    assert service.request_report(factory, NS, START, END).id == first.id
    report_id = retain(factory)
    with factory() as s:
        task = s.get(UploadRequest, first.id)
        task.status, task.latest_report_id = "ready", report_id
        s.commit()
    assert service.request_report(factory, NS, START, END).status == "ready"
    assert (
        service.request_report(factory, NS, START, END, refresh=True).status == "queued"
    )

    def broken(*a, **kw):
        raise ValueError("SECRET DO NOT PERSIST")

    monkeypatch.setattr(service, "reporting_client", broken)
    service.tick(factory)
    with factory() as s:
        task = s.get(UploadRequest, first.id)
        assert task.latest_report_id == report_id and task.status == "queued"
        assert "SECRET" not in task.last_error and task.retry_at


def test_failed_validation_retains_original_without_publishing(factory):
    with pytest.raises(IntegrationExecutionError):
        retain(factory, content(filter_name="All Transactions"))
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(UploadReport)) == 0
        assert s.scalar(select(AcquiredArtifact)).artifact_bytes == content(
            filter_name="All Transactions"
        )


def test_rejects_future_and_oversized_windows(factory):
    with pytest.raises(ValueError):
        service.request_report(factory, NS, START, START + timedelta(days=32))
    with pytest.raises(ValueError):
        service.request_report(factory, NS, END, START)


def test_api_requires_genuine_filter_and_sends_it(monkeypatch):
    from app.integration.sources.nmvs.reporting import ReportingApiError
    from app.integration.sources.nmvs.uploads.api import UploadClient

    client = UploadClient(
        "https://example.test/report", lambda: "unused", api_version="3.6"
    )
    try:
        definition = {"latestAvailableData": "2026-10-04T00:00:00Z", "parameters": []}
        monkeypatch.setattr(client, "definition", lambda: definition)
        with pytest.raises(ReportingApiError, match="genuine"):
            client.get_upload(START, END, title="test", created_at=START)
        definition["parameters"] = [{"id": "syntheticMonitoring", "type": "bool"}]
        sent = []
        monkeypatch.setattr(
            client, "get_pack", lambda params, **kw: sent.append(params)
        )
        client.get_upload(START, END, title="test", created_at=START)
        assert sent[0]["syntheticMonitoring"] is False
        assert sent[0]["endDateTime"] == "2026-10-03T00:00:00Z"
        definition["latestAvailableData"] = "2026-10-02T00:00:00Z"
        with pytest.raises(ReportingApiError, match="completed"):
            client.get_upload(START, END, title="test", created_at=START)
    finally:
        client.close()


def test_worker_success_and_restart_reuses_durable_title(factory, monkeypatch):
    task = service.request_report(factory, NS, START, END)
    calls = []

    class Client:
        _base_url = "https://example.test/report"

        def get_upload(self, start, end, **kwargs):
            calls.append(kwargs["title"])
            return SimpleNamespace(
                content=content(),
                report_uri=self._base_url + "/reports/one",
                report_metadata={
                    "request": {
                        "startDateTime": START.isoformat() + "Z",
                        "endDateTime": END.isoformat() + "Z",
                    }
                },
                requested_api_version="3.6",
                used_api_version="3.6",
            )

        def close(self):
            pass

    monkeypatch.setattr(service, "reporting_client", lambda *a, **kw: Client())
    with factory() as s:
        running = s.get(UploadRequest, task.id)
        running.status = "running"
        s.commit()
    assert service.tick(factory) == task.id
    with factory() as s:
        ready = s.get(UploadRequest, task.id)
        assert ready.status == "ready" and ready.latest_report_id
        assert s.scalar(select(UploadReport)).source_namespace == NS
    assert calls == [task.request_title]
    assert service.tick(factory) is None
