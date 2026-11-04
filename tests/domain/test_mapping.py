import hashlib
from datetime import date

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.core.db.models import (
    AcquiredArtifact,
    ArtifactContent,
    Base,
    ImportMutex,
    IntegrationJob,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.core.db.session import GuardedSession
from app.domain.mapping import MUTEX, MappingError, publish
from app.domain.models import (
    Batch,
    CurrentPublication,
    MappingRun,
    Product,
    ProductReferenceMatch,
    ProductSourceRecord,
    ProductVersion,
    SAIHolder,
    SAIPackage,
    SAIPreparation,
)
from app.integration.artifacts.storage import utcnow
from app.integration.sources.nmvs.parsing import record_hash

GTIN = "4006381333931"
OTHER_GTIN = "96385074"


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "mapping.db"))

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.create_function("DATABASE", 0, lambda: "smvs_operations")

    Base.metadata.create_all(engine)
    factory = sessionmaker(
        engine,
        class_=GuardedSession,
        configured_database="smvs_operations",
        expire_on_commit=False,
    )
    with factory() as s:
        s.add(ImportMutex(import_key=MUTEX))
        s.commit()
    yield factory
    engine.dispose()


def datasets(
    *,
    version="3",
    batch_version="1",
    product_code=GTIN,
    scheme="GTIN",
    duplicate=False,
    missing_product=False,
    ambiguous=False,
    sai_gtin=GTIN,
):
    product = {
        "Product Code Scheme": scheme,
        "Product Code": product_code,
        "Product Version Number": version,
        "Product Name": "WRONG NMVS NAME",
        "MAH Name": "WRONG NMVS MAH",
        "Product State": "Active",
        "Number Of Packs": "100",
        "Number Of Active Packs": "80",
    }
    batch = {
        "Product Code Scheme": scheme,
        "Product Code": product_code,
        "Product Version Number": batch_version,
        "Batch Id": "Lot-001",
        "Batch Expiry Date": "270000",
        "Batch State": "Active",
        "Number Of Packs": "100",
    }
    package = {
        "ZULASSUNGSNUMMER": "00001",
        "SEQUENZNUMMER": "01",
        "PACKUNGSCODE": "001",
        "GTIN_INDUSTRY": sai_gtin,
        "BESCHREIBUNG_DE_REFDATA": "Schweizer Packung",
        "BESCHREIBUNG_FR_REFDATA": "Emballage suisse",
        "ZULASSUNGSSTATUS": "Z",
    }
    return {
        "Products": []
        if missing_product
        else [product, dict(product)]
        if duplicate
        else [product],
        "Batches": [batch],
        "SAI_ADRESSEN": [
            {
                "PARTNER_NR": "0007",
                "FIRMENNAME": "Schweizer Inhaberin",
                "GLN_REFDATA": "1234567890128",
            }
        ],
        "SAI_PRAEPARATE": [
            {
                "ZULASSUNGSNUMMER": "00001",
                "PRAEPARATENAME": "Schweizer Präparat",
                "ZULASSUNGSINHABERIN": "0007",
                "ATC_CODE": "A01AA01",
            }
        ],
        "SAI_PACKUNGEN": [
            package,
            {
                **package,
                "PACKUNGSCODE": "002",
                "GTIN_INDUSTRY": GTIN if ambiguous else "",
            },
        ],
    }


def seed(
    sessions,
    data=None,
    *,
    snapshot_day=date(2026, 9, 26),
    sai_export="2026-10-05T03:02:27",
):
    data = datasets() if data is None else data
    identifiers = []
    with sessions() as s:
        for source, report, names in [
            ("NMVS", "DailySnapshot", ("Products", "Batches")),
            (
                "Refdata SAI",
                "SAIFullExport",
                ("SAI_ADRESSEN", "SAI_PRAEPARATE", "SAI_PACKUNGEN"),
            ),
        ]:
            job = IntegrationJob(
                source_name=source,
                channel_name="test",
                report_type=report,
                requested_snapshot_date=snapshot_day,
                status="succeeded",
                created_at=utcnow(),
            )
            s.add(job)
            s.flush()
            raw = f"synthetic-{source}-{job.id}".encode()
            content = ArtifactContent(
                sha256=hashlib.sha256(raw).hexdigest(),
                content_length=len(raw),
                artifact_bytes=raw,
                created_at=utcnow(),
            )
            s.add(content)
            s.flush()
            artifact = AcquiredArtifact(
                integration_job_id=job.id,
                content_id=content.id,
                source_name=source,
                channel_name="test",
                report_type=report,
                source_uri="https://synthetic.test/report",
                report_metadata={"exported_at_source": sai_export},
                received_at=utcnow(),
                processing_status="staged",
                created_at=utcnow(),
            )
            s.add(artifact)
            s.flush()
            run = ProcessingRun(
                artifact_id=artifact.id,
                run_type="initial_extraction",
                parser_version="test1",
                transform_version="none",
                status="succeeded",
                started_at=utcnow(),
            )
            s.add(run)
            s.flush()
            identifiers.append(run.id)
            for order, name in enumerate(names, 1):
                rows = data[name]
                ds = StagingDataset(
                    processing_run_id=run.id,
                    artifact_id=artifact.id,
                    source_dataset_name=name,
                    section_order=order,
                    source_headers=list(rows[0]) if rows else [],
                    row_count=len(rows),
                    extraction_status="extracted",
                    created_at=utcnow(),
                )
                s.add(ds)
                s.flush()
                for number, row in enumerate(rows, 1):
                    s.add(
                        StagingRow(
                            staging_dataset_id=ds.id,
                            source_row_number=number,
                            source_record_hash=record_hash(row),
                            raw_row_json=row,
                            created_at=utcnow(),
                        )
                    )
            s.flush()
        s.commit()
    return identifiers


def counts(sessions):
    with sessions() as s:
        return {
            m.__tablename__: s.scalar(select(func.count()).select_from(m))
            for m in (
                Product,
                ProductSourceRecord,
                ProductVersion,
                Batch,
                SAIHolder,
                SAIPreparation,
                SAIPackage,
                ProductReferenceMatch,
                MappingRun,
            )
        }


def test_links_swiss_names_and_batch_version_and_repeat_is_noop(sessions):
    snapshot, sai = seed(sessions)
    first = publish(sessions, snapshot, sai, "synthetic-nmvs")
    before = counts(sessions)
    repeated = publish(sessions, snapshot, sai, "synthetic-nmvs")
    assert repeated.id == first.id and counts(sessions) == before
    with sessions() as s:
        assert s.scalar(select(Product)).gtin14 == "04006381333931"
        assert s.scalar(select(ProductSourceRecord)).reported_version == 3
        batch = s.scalar(select(Batch))
        version = s.get(ProductVersion, batch.product_version_id)
        assert (
            version.version_number == 1
            and version.detail_status == "batch_reference_only"
        )
        assert "Product Name" not in version.evidence
        assert batch.expiry_source_text == "270000"
        match = s.scalar(select(ProductReferenceMatch))
        package = s.get(SAIPackage, match.sai_package_id)
        prep = s.get(SAIPreparation, package.preparation_id)
        assert match.match_status == "matched_sai"
        assert prep.preparation_name == "Schweizer Präparat"
        assert s.get(SAIHolder, prep.holder_id).company_name == "Schweizer Inhaberin"
        assert (
            s.scalar(select(func.count()).select_from(SAIPackage)) == 2
        )  # No-GTIN package retained.


@pytest.mark.parametrize(
    "options,status",
    [
        ({"product_code": OTHER_GTIN}, "no_sai_match"),
        ({"product_code": "not-a-gtin"}, "not_gtin_matchable"),
        ({"product_code": "PPN-001", "scheme": "PPN"}, "not_gtin_matchable"),
        ({"ambiguous": True}, "ambiguous"),
    ],
)
def test_no_loss_or_false_swiss_foreign_classification(sessions, options, status):
    snapshot, sai = seed(sessions, datasets(**options))
    publish(sessions, snapshot, sai, "synthetic-nmvs")
    with sessions() as s:
        match = s.scalar(select(ProductReferenceMatch))
        assert match.match_status == status and match.sai_package_id is None
        assert s.scalar(select(func.count()).select_from(Product)) == 1
        assert s.scalar(select(func.count()).select_from(Batch)) == 1


def test_duplicate_input_failure_retains_current_publication(sessions):
    original = publish(sessions, *seed(sessions), "synthetic-nmvs")
    before = counts(sessions)
    new = seed(sessions, datasets(duplicate=True), snapshot_day=date(2026, 9, 27))
    with pytest.raises(MappingError):
        publish(sessions, *new, "synthetic-nmvs")
    after = counts(sessions)
    assert {k: v for k, v in after.items() if k != "mapping_runs"} == {
        k: v for k, v in before.items() if k != "mapping_runs"
    }
    with sessions() as s:
        assert s.get(CurrentPublication, "product-batch").mapping_run_id == original.id
        assert (
            s.scalar(select(MappingRun).order_by(MappingRun.id.desc())).status
            == "failed"
        )
        assert s.scalar(select(ProductSourceRecord)).is_observed == 1


def test_old_version_pmd_details_are_retained_not_filled_from_new_version(sessions):
    publish(
        sessions,
        *seed(sessions, datasets(version="1", batch_version="1")),
        "synthetic-nmvs",
    )
    publish(
        sessions,
        *seed(
            sessions,
            datasets(version="3", batch_version="1"),
            snapshot_day=date(2026, 9, 27),
        ),
        "synthetic-nmvs",
    )
    with sessions() as s:
        old = s.scalar(select(ProductVersion).where(ProductVersion.version_number == 1))
        assert old.detail_status == "pmd_observed"
        assert old.evidence["Product Version Number"] == "1"
        assert s.scalar(select(func.count()).select_from(Product)) == 1
        assert s.scalar(select(func.count()).select_from(Batch)) == 1


def test_older_inputs_and_unapproved_correction_do_not_replace_current(sessions):
    initial = seed(sessions)
    first = publish(sessions, *initial, "synthetic-nmvs")
    for day in [date(2026, 9, 25), date(2026, 9, 26)]:
        other = seed(sessions, snapshot_day=day)
        with pytest.raises(MappingError):
            publish(sessions, *other, "synthetic-nmvs")
    with sessions() as s:
        assert s.get(CurrentPublication, "product-batch").mapping_run_id == first.id


def test_disappearance_keeps_identity_and_marks_not_observed(sessions):
    publish(sessions, *seed(sessions), "synthetic-nmvs")
    empty = datasets()
    empty["Products"] = []
    empty["Batches"] = []
    publish(
        sessions,
        *seed(sessions, empty, snapshot_day=date(2026, 9, 27)),
        "synthetic-nmvs",
    )
    with sessions() as s:
        assert s.scalar(select(ProductSourceRecord)).is_observed == 0
        assert s.scalar(select(Batch)).is_observed == 0
        assert s.scalar(select(func.count()).select_from(Product)) == 1


def test_transaction_rollback_when_batch_insert_fails(sessions):
    first = publish(sessions, *seed(sessions), "synthetic-nmvs")
    next_input = seed(sessions, datasets(version="4"), snapshot_day=date(2026, 9, 27))
    engine = sessions.kw["bind"]

    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO batches"):
            raise RuntimeError("secret source values must not leak")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(MappingError) as failure:
            publish(sessions, *next_input, "synthetic-nmvs")
        assert "secret" not in str(failure.value)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with sessions() as s:
        assert s.get(CurrentPublication, "product-batch").mapping_run_id == first.id
        assert s.scalar(select(ProductSourceRecord)).reported_version == 3
        assert s.scalar(select(func.count()).select_from(ProductVersion)) == 2


def test_case_sensitive_batch_codes_have_distinct_identity(sessions):
    data = datasets()
    data["Batches"].append({**data["Batches"][0], "Batch Id": "lot-001"})
    publish(sessions, *seed(sessions, data), "synthetic-nmvs")
    assert counts(sessions)["batches"] == 2


@pytest.mark.parametrize("raw", ["-1", "-2", "", "0", "unavailable"])
def test_unresolved_source_versions_are_preserved_without_fabricating_pmd(
    sessions, raw
):
    snapshot, sai = seed(sessions, datasets(version=raw, batch_version=raw))
    publish(sessions, snapshot, sai, "synthetic-nmvs")
    with sessions() as s:
        source = s.scalar(select(ProductSourceRecord))
        version = s.scalar(select(ProductVersion))
        assert source.reported_version is None and source.reported_version_text == raw
        assert version.version_number is None and version.source_version_value == raw
        assert version.detail_status == "unresolved_source_value"
        assert s.scalar(select(func.count()).select_from(Batch)) == 1
