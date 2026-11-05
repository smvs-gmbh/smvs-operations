import io
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select

from app.core.db.models import AcquiredArtifact, ImportMutex, ProcessingRun, StagingRow
from app.domain.activity.mapping import MUTEX, publish_activity
from app.domain.activity.service import pending_periods
from app.domain.mapping import MappingError
from app.domain.models import ActivityDay, ActivityFact, ActivityPublication
from app.integration.idempotency import result_run_id
from app.integration.sources.nmvs.activity.acquisition import UserActivityAcquisition
from app.integration.sources.nmvs.activity.parsing import parse_activity
from app.integration.sources.nmvs.activity.processing import process_activity
from tests.domain.test_mapping import sessions  # noqa: F401

NS = "nmvs-origin:https://example.test"
START = date(2026, 8, 1)


def workbook(
    *,
    count=12,
    exception=2,
    request="2026-09-01T12:00:00Z",
    synthetic="False",
    extra=False,
    empty=False,
    duplicate=False,
    omit=False,
):
    w = Workbook()
    w.remove(w.active)
    s = w.create_sheet("Report Header")
    s.append(["Report Header", "Value"])
    metadata = {
        "Report Type": "User Activity Report",
        "Report Name": "Test report",
        "Date Requested (UTC)": request,
        "Start Date (UTC)": "2026-08-01",
        "End Date (UTC)": "2026-08-02",
        "Synthetic Monitoring": synthetic,
        "Activity Days Only": "False",
        **{
            k: "-"
            for k in (
                "Business Processes",
                "Reports",
                "Organisation Types",
                "Organisation ID",
                "IMT Market",
                "Location ID",
                "Client ID/Username",
            )
        },
    }
    for k, v in metadata.items():
        s.append([k, v])
    for name, dims, values in [
        (
            "Verification",
            [
                "Organisation Type",
                "Organisation ID",
                "Organisation Name",
                "Business Process",
            ],
            ["Wholesaler", "05", "Example Org", "Single Pack Verification"],
        ),
        (
            "IMT Fulfilment",
            ["Organisation Type", "Market", "Business Process"],
            ["Remote Location", "DE", "IMT Verification"],
        ),
    ]:
        s = w.create_sheet(name)
        headers = dims + [
            f"2026-08-0{d} {metric}"
            for d in (1, 2)
            for metric in ("Exception", "Total")
        ]
        s.append(headers[:-1] if omit else headers)
        if not empty:
            row = values + [exception, count, 0, 0]
            s.append(row[:-1] if omit else row)
            if duplicate:
                s.append(row)
        if extra and name == "Verification":
            s.append(
                [
                    "Wholesaler",
                    "05",
                    "Example Org",
                    "Bulk Pack Verification - Avg. No. Packs",
                    0,
                    27.5,
                    0,
                    0,
                ]
            )
            s.append(
                [
                    "Wholesaler",
                    "05",
                    "Example Org",
                    "Bulk Pack Verification - Total No. Packs",
                    0,
                    55,
                    0,
                    0,
                ]
            )
    b = io.BytesIO()
    w.save(b)
    return b.getvalue()


class Client:
    api_version = "3.3"
    _base_url = "https://example.test/report"

    def __init__(self, data):
        self.data = data

    def get_activity(self, start, end):
        return SimpleNamespace(
            content=self.data,
            report_uri=self._base_url + "/reports/test",
            content_type="application/xlsx",
            report_metadata={
                "request": {"startDate": str(start), "endDate": str(end)},
                "report": {"title": "Test report"},
            },
            used_api_version="3.3",
        )


def acquire(factory, data):
    with factory() as s:
        job = UserActivityAcquisition(Client(data)).run(
            s, START, START + timedelta(days=1)
        )
        r = s.scalar(
            select(ProcessingRun)
            .join(AcquiredArtifact)
            .where(AcquiredArtifact.integration_job_id == job.id)
        )
        return r.id


@pytest.fixture
def factory(sessions):  # noqa: F811 - shared pytest fixture
    with sessions() as s:
        s.add(ImportMutex(import_key=MUTEX))
        s.commit()
    return sessions


@pytest.mark.parametrize(
    "kwargs",
    [
        {"count": None},
        {"count": 1.5},
        {"count": -1},
        {"exception": 20},
        {"duplicate": True},
        {"omit": True},
    ],
)
def test_reject_invalid_counts_dimensions_or_missing_columns(kwargs):
    with pytest.raises((ValueError, TypeError)):
        parse_activity(workbook(**kwargs))


def test_bulk_measures_keep_decimal_separately_from_transactions():
    parsed = parse_activity(workbook(extra=True))
    avg = parsed.datasets[0].rows[2]
    assert avg["Metric Kind"] == "mean_pack_count" and avg["Count"] == "27.5"


def test_repeated_acquisition_replay_and_publication_are_idempotent(factory):
    data = workbook(extra=True)
    first = acquire(factory, data)
    pub = publish_activity(factory, first, NS)
    second = acquire(factory, data)
    with factory() as s:
        assert result_run_id(s.get(ProcessingRun, second)) == first
        before = s.scalar(select(func.count()).select_from(StagingRow))
        artifact_id = s.get(ProcessingRun, first).artifact_id
    with factory() as s:
        r = process_activity(s, artifact_id)
    assert publish_activity(factory, r.id, NS).id == pub.id
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(StagingRow)) == before
        assert s.scalar(select(func.count()).select_from(ActivityDay)) == 4
        assert s.scalar(select(func.count()).select_from(ActivityPublication)) == 1
        assert s.scalar(select(func.sum(ActivityFact.transaction_count))) == 24
        assert s.scalar(select(func.count()).select_from(ActivityFact)) == 8


def test_correction_replaces_counts_and_removes_absent_rows_without_resurrecting_old(
    factory,
):
    first = acquire(factory, workbook())
    publish_activity(factory, first, NS)
    correction = acquire(factory, workbook(empty=True, request="2026-09-02T12:00:00Z"))
    pub = publish_activity(factory, correction, NS)
    publish_activity(factory, first, NS)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(ActivityFact)) == 0
        assert {d.publication_id for d in s.scalars(select(ActivityDay))} == {pub.id}


def test_changed_bytes_same_day_upsert_and_stale_or_filtered_inputs_refused(factory):
    publish_activity(factory, acquire(factory, workbook()), NS)
    publish_activity(
        factory,
        acquire(factory, workbook(count=25, request="2026-09-02T12:00:00Z")),
        NS,
    )
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(ActivityFact)) == 4
        assert s.scalar(select(func.sum(ActivityFact.transaction_count))) == 50
    stale = acquire(factory, workbook(count=10, request="2026-08-30T12:00:00Z"))
    with pytest.raises(MappingError):
        publish_activity(factory, stale, NS)
    all_transactions = acquire(
        factory, workbook(synthetic="All Transactions", request="2026-09-03T12:00:00Z")
    )
    with pytest.raises(MappingError):
        publish_activity(factory, all_transactions, NS)
    with pytest.raises(MappingError):
        publish_activity(factory, stale, "wrong-environment")


def test_invalid_workbook_bytes_are_retained_before_extraction_failure(factory):
    from app.integration.failures import IntegrationExecutionError

    with pytest.raises(IntegrationExecutionError):
        acquire(factory, b"not a workbook")
    with factory() as s:
        a = s.scalar(select(AcquiredArtifact))
        assert a.artifact_bytes == b"not a workbook"
        assert s.scalar(select(ProcessingRun.status)) == "failed"


def test_scheduler_backfill_and_gap_detection_and_recent_corrections(factory):
    assert pending_periods(factory, NS, today=date(2026, 8, 3)) == [
        (date(2026, 5, 5), date(2026, 6, 3)),
        (date(2026, 6, 4), date(2026, 7, 3)),
        (date(2026, 7, 4), date(2026, 8, 2)),
    ]
    publish_activity(factory, acquire(factory, workbook()), NS)
    periods = pending_periods(factory, NS, today=date(2026, 8, 12))
    wanted = {
        start + timedelta(days=i)
        for start, end in periods
        for i in range((end - start).days + 1)
    }
    assert date(2026, 8, 1) not in wanted and date(2026, 8, 2) not in wanted
    assert date(2026, 8, 3) in wanted and date(2026, 8, 11) in wanted
