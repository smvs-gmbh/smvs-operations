import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.core.db.models import AcquiredArtifact, ImportMutex, ProcessingRun, StagingRow
from app.domain.exceptions.mapping import MUTEX, publish_exceptions
from app.domain.models import ExceptionPublication, ExceptionRevision, NMVSException
from app.integration.failures import IntegrationExecutionError
from app.integration.sources.nmvs.exceptions.acquisition import ExceptionsAcquisition
from app.integration.sources.nmvs.exceptions.parsing import parse_pages, source_time
from app.integration.sources.nmvs.exceptions.processing import process_exceptions
from tests.domain.test_mapping import sessions  # noqa: F401

NS = "nmvs-origin:https://example.test"
START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2026, 10, 31, tzinfo=UTC)


def alert(identifier="CH-test-001", **updates):
    return {
        "uniqueAlertID": identifier,
        "alertDateTime": "2026-10-05T10:20:30.123Z",
        "transactionID": "tx-1",
        "errorCode": "A2",
        "errorMessage": "Batch not found",
        "productCodeScheme": "GTIN",
        "productCode": "4006381333931",
        "serialNumber": "000SnA",
        "providedBatchNumber": "BAD",
        "storedBatchNumber": "Lot-001",
        "organisationID": 5,
        "sourceLocationID": "request-location",
        "packLastUpdateLocationID": "last-update-location",
        "sourceMarket": "CH",
        "manualEntry": False,
        "isIntermarket": True,
        "sourceBusinessProcess": "National System Single Pack API",
        "productName": "WRONG NMVS NAME",
        **updates,
    }


def page(rows, *, number=1, pages=1, total=None, truncated=False, records=None):
    return {
        "page": number,
        "pages": pages,
        "pageSize": 1000,
        "records": len(rows) if records is None else records,
        "totalRecords": len(rows) if total is None else total,
        "isTruncated": truncated,
        "data": rows,
    }


class Client:
    api_version = "1.0"
    _base_url = "https://exceptions.example.test"

    def __init__(self, pages):
        self.pages = pages

    def request(self, start, end):
        return "request-test", {
            "startTimestamp": start.isoformat(),
            "endTimestamp": end.isoformat(),
        }

    def page(self, request_id, number):
        return httpx.Response(
            200, json=self.pages[number - 1], headers={"emvs-api-version": "1.0"}
        )

    def escalate(self, rid):
        return "full-request-test"


def acquire(factory, pages):
    with factory() as s:
        return ExceptionsAcquisition(Client(pages), NS).run(s, START, END)[1].id


@pytest.fixture
def factory(sessions):  # noqa: F811 - shared guarded fixture
    with sessions() as s:
        s.add(ImportMutex(import_key=MUTEX))
        s.commit()
    return sessions


def test_complete_pages_accept_actual_query_level_records_and_refuse_partial_or_duplicate():
    data = [
        json.dumps(page([alert("one")], pages=2, total=2, records=2)).encode(),
        json.dumps(
            page([alert("two")], number=2, pages=2, total=2, records=2)
        ).encode(),
    ]
    assert len(parse_pages(data)) == 2
    with pytest.raises(ValueError):
        parse_pages(data[:1])
    with pytest.raises(ValueError):
        parse_pages([json.dumps(page([alert(), alert()])).encode()])
    with pytest.raises(ValueError):
        parse_pages([json.dumps(page([alert()], truncated=True)).encode()])


def test_repeated_query_replay_and_publication_do_not_duplicate_business_rows(factory):
    first = acquire(factory, [page([alert()])])
    p1 = publish_exceptions(factory, first, NS)
    second = acquire(factory, [page([alert()])])
    publish_exceptions(factory, second, NS)
    with factory() as s:
        artifact_id = s.get(ProcessingRun, first).artifact_id
        before = s.scalar(select(func.count()).select_from(StagingRow))
    with factory() as s:
        replay = process_exceptions(s, artifact_id)
    assert publish_exceptions(factory, replay.id, NS).id == p1.id
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(StagingRow)) == before
        assert s.scalar(select(func.count()).select_from(NMVSException)) == 1
        assert s.scalar(select(func.count()).select_from(ExceptionRevision)) == 1
        record = s.scalar(select(NMVSException))
        assert record.gtin14 == "04006381333931" and record.serial_number == "000SnA"
        assert record.source_location_id != record.last_update_location_id
        assert record.alert_at.microsecond == 123000


def test_changed_payload_retained_and_stale_replay_does_not_restore_old_selection(
    factory,
):
    first = acquire(factory, [page([alert()])])
    publish_exceptions(factory, first, NS)
    # Establish an unambiguous later query selection on this deterministic clock fixture.
    with factory() as s:
        old = s.scalar(select(NMVSException))
        old.selection_time -= timedelta(seconds=1)
        s.commit()
    second = acquire(factory, [page([alert(errorMessage="Corrected source details")])])
    publish_exceptions(factory, second, NS)
    publish_exceptions(factory, first, NS)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(NMVSException)) == 1
        assert s.scalar(select(func.count()).select_from(ExceptionRevision)) == 2
        assert (
            s.scalar(select(NMVSException.error_message)) == "Corrected source details"
        )


def test_invalid_row_and_incomplete_pagination_retain_source_without_publication(
    factory,
):
    with pytest.raises(IntegrationExecutionError):
        acquire(factory, [page([alert(uniqueAlertID="")])])
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(AcquiredArtifact)) == 1
        assert s.scalar(select(func.count()).select_from(NMVSException)) == 0
    partial = [page([alert()], pages=2, total=2), page([], number=2, pages=2, total=2)]
    with pytest.raises(IntegrationExecutionError):
        acquire(factory, partial)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(ExceptionPublication)) == 0
        assert s.scalar(select(func.count()).select_from(StagingRow)) == 0


def test_unknown_time_is_retained_and_absence_never_deletes_existing_exception(factory):
    identifier = acquire(factory, [page([alert(alertDateTime="not a timestamp")])])
    publish_exceptions(factory, identifier, NS)
    empty = acquire(factory, [page([])])
    publish_exceptions(factory, empty, NS)
    with factory() as s:
        record = s.scalar(select(NMVSException))
        assert record.alert_at is None and record.timestamp_status == "invalid"
        assert record.evidence["alertDateTime"] == "not a timestamp"
    assert source_time("2026-10-05T10:00:00")[1] == "missing_offset"


def test_authority_mismatch_is_refused(factory):
    from app.domain.mapping import MappingError

    r = acquire(factory, [page([alert()])])
    with pytest.raises(MappingError):
        publish_exceptions(factory, r, "another-authority")


def test_truncated_query_escalates_before_accepting_only_the_full_manifest(factory):
    class EscalatedClient(Client):
        calls = 0
        escalations = 0

        def page(self, request_id, number):
            self.calls += 1
            payload = page([alert()], truncated=self.calls == 1)
            return httpx.Response(200, json=payload)

        def escalate(self, rid):
            self.escalations += 1
            return "escalated"

    client = EscalatedClient([])
    with factory() as s:
        _, run = ExceptionsAcquisition(client, NS).run(s, START, END)
    pub = publish_exceptions(factory, run.id, NS)
    assert client.escalations == 1 and pub.statistics["new_exceptions"] == 1
    with factory() as s:
        assert (
            s.scalar(select(func.count()).select_from(AcquiredArtifact)) == 3
        )  # partial, full, manifest


def test_source_alert_datetime_preserves_microseconds_in_mysql_model():
    from sqlalchemy.dialects import mysql

    type_ = NMVSException.__table__.c.alert_at.type.dialect_impl(mysql.dialect())
    assert type_.fsp == 6
