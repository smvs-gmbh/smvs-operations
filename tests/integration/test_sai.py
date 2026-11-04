import io
import zipfile
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.core.db.models import (
    AcquiredArtifact,
    ArtifactContent,
    Base,
    IntegrationJob,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.core.db.safety import DatabaseSafetyError
from app.core.db.session import GuardedSession
from app.integration.failures import IntegrationExecutionError
from app.integration.sources.sai.acquisition import SAIAcquisition
from app.integration.sources.sai.client import (
    PAGE_URL,
    SAIClient,
    SAIError,
    latest_export,
)
from app.integration.sources.sai.parsing import (
    NAMESPACE,
    TARGETS,
    normalize_gtin14,
    parse_sai,
)
from app.integration.sources.sai.processing import replay_sai


def listing(*entries):
    return (
        "<table>"
        + "".join(
            f'<tr><th data-url="{url}">{name}</th><td data-url="{url}"></td></tr>'
            for name, url in entries
        )
        + "</table>"
    )


NAME = "SAI-Export_20261005-030227.zip"
LINK = "/download/structuredexportzip/9029"
HTML = listing((NAME, LINK))


def archive(*, broken=None, missing=None, duplicate=False):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for filename, root, row in TARGETS:
            if filename == missing:
                continue
            xml = (
                f'<{root} xmlns="{NAMESPACE}" schemaVersion="3.2"><{row}>'
                f"<IDENTIFIER>00001</IDENTIFIER><NAME> Ä &amp; B </NAME><EMPTY/>"
                f"</{row}></{root}>"
            ).encode()
            if filename == TARGETS[0][0] and broken is not None:
                xml = broken
            z.writestr("SAI/" + filename, xml)
            if duplicate and filename == TARGETS[0][0]:
                z.writestr("other/" + filename, xml)
    return output.getvalue()


def test_discovery_uses_full_timestamp_not_row_order():
    html = listing(
        ("SAI-Export_20261005-020000.zip", "/download/structuredexportzip/1"),
        (NAME, LINK),
        ("SAI-Export_20260905-090000.zip", "/download/structuredexportzip/3"),
    )
    found = latest_export(html)
    assert found.filename == NAME
    assert found.url == "https://sai.refdata.ch" + LINK
    assert found.exported_at.hour == 3


@pytest.mark.parametrize(
    "html",
    [
        "<html>No exports</html>",
        listing((NAME, "https://evil.test/download/structuredexportzip/1")),
        listing((NAME, "//sai.refdata.ch.evil.test/download/structuredexportzip/1")),
        listing((NAME, LINK + "?unexpected=1")),
        listing((NAME, LINK), (NAME, "/download/structuredexportzip/2")),
        listing(("SAI-Export_20261305-030000.zip", LINK)),
    ],
)
def test_bad_or_ambiguous_listing_fails(html):
    with pytest.raises(SAIError):
        latest_export(html)


def test_http_client_discovers_and_downloads_actual_listing_link():
    requested = []

    def handler(request):
        requested.append(str(request.url))
        return (
            httpx.Response(200, text=HTML)
            if str(request.url) == PAGE_URL
            else httpx.Response(200, content=archive())
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = SAIClient(http)
        result = client.download(client.discover())
        assert parse_sai(result[0]).file_metadata["delivery_mode"] == "full"
    assert requested == [PAGE_URL, "https://sai.refdata.ch" + LINK]


@pytest.mark.parametrize("status", [302, 404, 500])
def test_http_errors_and_redirects_fail_without_following(status):
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(status, headers={"Location": "https://evil.test"})

    with (
        httpx.Client(
            transport=httpx.MockTransport(handler), follow_redirects=True
        ) as http,
        pytest.raises(SAIError),
    ):
        SAIClient(http).discover()
    assert len(calls) == 1


def test_response_size_limit():
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, content=b"12345")
            )
        ) as http,
        pytest.raises(SAIError),
    ):
        SAIClient(http)._get(PAGE_URL, 4)


def test_source_values_and_dataset_order_preserved():
    result = parse_sai(archive())
    assert [d.source_dataset_name for d in result.datasets] == [
        root for _, root, _ in TARGETS
    ]
    assert result.datasets[0].rows[0] == {
        "IDENTIFIER": "00001",
        "NAME": " Ä & B ",
        "EMPTY": "",
    }


@pytest.mark.parametrize(
    "content",
    [
        b"not a ZIP",
        archive(missing=TARGETS[0][0]),
        archive(duplicate=True),
        archive(broken=b'<!DOCTYPE test [<!ENTITY x "danger">]><test>&x;</test>'),
        archive(broken=b"<wrong/>"),
        archive(
            broken=f'<SAI_PRAEPARATE xmlns="{NAMESPACE}" schemaVersion="3.2"/>'.encode()
        ),
        archive(
            broken=f'<SAI_PRAEPARATE xmlns="{NAMESPACE}" schemaVersion="3.2"><PRAEPARAT><X>1</X><X>2</X></PRAEPARAT></SAI_PRAEPARATE>'.encode()
        ),
    ],
)
def test_invalid_archive_or_structure_rejected(content):
    with pytest.raises(SAIError):
        parse_sai(content)


@pytest.mark.parametrize(
    "source,expected",
    [
        ("4006381333931", "04006381333931"),
        ("96385074", "00000096385074"),
        ("04006381333931", "04006381333931"),
        ("036000291452", "00036000291452"),
        (" 4006381333931 ", "04006381333931"),
        ("", None),
        (None, None),
    ],
)
def test_gtin_normalization(source, expected):
    assert normalize_gtin14(source) == expected


@pytest.mark.parametrize(
    "source", ["4006381333932", "123", "Ａ００６３８１３３３９３１", "000000000000000"]
)
def test_invalid_gtin_rejected(source):
    with pytest.raises(SAIError):
        normalize_gtin14(source)


@pytest.fixture
def database():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.create_function("DATABASE", 0, lambda: "smvs_operations")

    @event.listens_for(engine, "begin")
    def begin(connection):
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def source(content=None):
    mock = Mock()
    mock.discover.return_value = latest_export(HTML)
    mock.download.return_value = (
        content if content is not None else archive(),
        "application/zip",
    )
    return mock


def test_acquisition_reacquisition_and_offline_replay(database):
    with GuardedSession(
        database, configured_database="smvs_operations", expire_on_commit=False
    ) as session:
        client = source()
        first = SAIAcquisition(client).run(session)
        second = SAIAcquisition(client).run(session)
        assert first.status == second.status == "succeeded"
        artifact_id = session.scalar(
            select(AcquiredArtifact.id).where(
                AcquiredArtifact.integration_job_id == first.id
            )
        )
        session.rollback()
        client.download.side_effect = AssertionError("Replay must not contact source")
        run = replay_sai(session, artifact_id)
        assert run.status == "succeeded"
        assert run.reused_from_run_id is not None
    with Session(database) as observer:
        assert observer.scalar(select(func.count()).select_from(ArtifactContent)) == 1
        assert observer.scalar(select(func.count()).select_from(AcquiredArtifact)) == 2
        assert observer.scalar(select(func.count()).select_from(StagingRow)) == 4
        assert observer.scalar(select(func.count()).select_from(ProcessingRun)) == 3


def test_parse_failure_retains_archive_and_records_failure(database):
    with GuardedSession(database, configured_database="smvs_operations") as session:
        with pytest.raises(IntegrationExecutionError) as failure:
            SAIAcquisition(source(b"bad ZIP")).run(session)
        assert failure.value.failure_recorded
        assert failure.value.stage == "extraction"
    with Session(database) as observer:
        assert observer.scalar(select(AcquiredArtifact)).artifact_bytes == b"bad ZIP"
        assert observer.scalar(select(ProcessingRun)).status == "failed"
        assert observer.scalar(select(func.count()).select_from(StagingRow)) == 0


def test_partial_staging_is_rolled_back_and_metadata_survives(database):
    calls = []

    @event.listens_for(database, "before_cursor_execute")
    def fail_second_batch(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO staging_rows"):
            calls.append(statement)
            if len(calls) == 2:
                raise ValueError("Synthetic failure must not leak")

    with GuardedSession(database, configured_database="smvs_operations") as session:
        with pytest.raises(IntegrationExecutionError) as failure:
            SAIAcquisition(source()).run(session)
        assert failure.value.failure_recorded
        assert "Synthetic" not in str(failure.value)
    with Session(database) as observer:
        assert observer.scalar(select(func.count()).select_from(StagingRow)) == 0
        assert observer.scalar(select(func.count()).select_from(StagingDataset)) == 0
        assert (
            observer.scalar(select(ProcessingRun)).file_metadata["delivery_mode"]
            == "full"
        )


def test_discovery_failure_durable_and_plain_session_rejected(database):
    client = source()
    client.discover.side_effect = SAIError("No export")
    with Session(database) as unsafe, pytest.raises(DatabaseSafetyError):
        SAIAcquisition(client).run(unsafe)
    with GuardedSession(database, configured_database="smvs_operations") as session:
        with pytest.raises(IntegrationExecutionError) as failure:
            SAIAcquisition(client).run(session)
        assert failure.value.stage == "discovery"
        assert failure.value.failure_recorded
    with Session(database) as observer:
        assert observer.scalar(select(IntegrationJob)).status == "failed"
