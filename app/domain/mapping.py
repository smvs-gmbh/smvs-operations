"""Atomic, idempotent publication of the selected Snapshot + SAI working set."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.db.models import (
    AcquiredArtifact,
    ImportMutex,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.core.db.session import require_runtime_session
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
from app.integration.idempotency import result_run_id
from app.integration.sources.sai.parsing import normalize_gtin14

MAPPING_VERSION = "product-batch-sai-1"
MUTEX = "mapping:product-batch"


class MappingError(ValueError):
    pass


def key(*parts) -> str:
    return hashlib.sha256(
        json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def required(row: dict, name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise MappingError("Required source identifier is missing or invalid.")
    return value


def integer(value, *, required_value=False, maximum=9223372036854775807):
    if value is None or value == "":
        if required_value:
            raise MappingError("Required numeric source value is missing.")
        return None
    text = str(value).strip()
    if not text.isascii() or not text.isdigit() or int(text) > maximum:
        raise MappingError("Numeric source value is invalid.")
    return int(text)


def gtin(value):
    try:
        return normalize_gtin14(value)
    except ValueError:
        return None  # Keep source records with invalid/missing identifiers.


def source_version(value):
    raw = value if isinstance(value, str) else "" if value is None else str(value)
    if len(raw) > 100:
        raise MappingError("Source version value exceeds the supported length.")
    text = raw.strip()
    number = int(text) if text.isascii() and text.isdigit() else None
    if number is not None and not 1 <= number <= 2147483647:
        number = None
    return raw, number


def version_identity(sk, value):
    raw, number = source_version(value)
    return (
        key(sk, "number", number)
        if number is not None
        else key(sk, "unresolved_source_value", raw)
    )


def canonical(session, identifier, source, report):
    run = session.get(ProcessingRun, identifier)
    if run is None or run.status != "succeeded":
        raise MappingError("Mapping requires successful source processing.")
    original_artifact = session.get(AcquiredArtifact, run.artifact_id)
    resolved = session.get(ProcessingRun, result_run_id(run))
    if (
        resolved is None
        or resolved.status != "succeeded"
        or resolved.reused_from_run_id is not None
    ):
        raise MappingError("Invalid source result reference.")
    artifact = session.get(AcquiredArtifact, resolved.artifact_id)
    if (artifact.source_name, artifact.report_type) != (source, report):
        raise MappingError("Unexpected source processing type.")
    if (
        artifact.content_id,
        artifact.source_name,
        artifact.channel_name,
        artifact.report_type,
        resolved.parser_version,
        resolved.transform_version,
    ) != (
        original_artifact.content_id,
        original_artifact.source_name,
        original_artifact.channel_name,
        original_artifact.report_type,
        run.parser_version,
        run.transform_version,
    ):
        raise MappingError("Inconsistent source result reference.")
    return resolved, artifact


def source_rows(session, run_id, name):
    dataset = session.scalar(
        select(StagingDataset).where(
            StagingDataset.processing_run_id == run_id,
            StagingDataset.source_dataset_name == name,
        )
    )
    if dataset is None or dataset.extraction_status != "extracted":
        raise MappingError("Required source dataset is unavailable.")
    rows = session.execute(
        select(StagingRow.id, StagingRow.raw_row_json)
        .where(StagingRow.staging_dataset_id == dataset.id)
        .order_by(StagingRow.source_row_number)
    ).all()
    if len(rows) != dataset.row_count:
        raise MappingError("Source dataset completeness check failed.")
    return rows


def upsert(session, model, rows, unique, *, preserve=()):
    if not rows:
        return
    table = model.__table__
    for offset in range(0, len(rows), 500):
        batch = rows[offset : offset + 500]
        columns = [c for c in batch[0] if c not in unique and c not in preserve]
        dialect = session.bind.dialect.name
        if dialect == "mysql":
            statement = mysql_insert(table).values(batch)
            statement = statement.on_duplicate_key_update(
                **{c: statement.inserted[c] for c in columns}
            )
        elif dialect == "sqlite":  # In-memory/file database doubles used by tests.
            statement = sqlite_insert(table).values(batch)
            statement = statement.on_conflict_do_update(
                index_elements=unique, set_={c: statement.excluded[c] for c in columns}
            )
        else:
            raise MappingError("Unsupported mapping database dialect.")
        session.execute(statement)


def ids(session, model, column):
    return dict(session.execute(select(getattr(model, column), model.id)).all())


def source_key(namespace, row):
    return key(
        namespace, required(row, "Product Code Scheme"), required(row, "Product Code")
    )


def unique_rows(rows, identity):
    seen = set()
    for _, row in rows:
        value = identity(row)
        if value in seen:
            raise MappingError("Conflicting duplicate source key; publication refused.")
        seen.add(value)


def selected(row, names):
    return {name: row[name] for name in names if name in row}


def publish(
    session_factory,
    snapshot_id: int,
    sai_id: int,
    namespace: str,
    *,
    mapping_version=MAPPING_VERSION,
    allow_same_day_correction=False,
) -> MappingRun:
    if not namespace or len(namespace) > 255:
        raise MappingError("An explicit source namespace is required.")
    with session_factory() as lock_session:
        require_runtime_session(lock_session)
        lock_session.execute(
            select(ImportMutex.import_key)
            .where(ImportMutex.import_key == MUTEX)
            .with_for_update()
        ).scalar_one()
        with session_factory() as session:
            require_runtime_session(session)
            run_id = None
            try:
                snapshot, snapshot_artifact = canonical(
                    session, snapshot_id, "NMVS", "DailySnapshot"
                )
                sai, sai_artifact = canonical(
                    session, sai_id, "Refdata SAI", "SAIFullExport"
                )
                snapshot_date = (
                    snapshot_artifact.integration_job.requested_snapshot_date
                )
                exported_at = datetime.fromisoformat(
                    sai_artifact.report_metadata["exported_at_source"]
                )
                if snapshot_date is None or exported_at.tzinfo is not None:
                    raise MappingError(
                        "Source publication time is unavailable or incompatible."
                    )
                input_key = key(namespace, snapshot.id, sai.id, mapping_version)
                existing = session.scalar(
                    select(MappingRun).where(MappingRun.input_key == input_key)
                )
                if existing is not None and existing.status == "succeeded":
                    session.expunge(existing)
                    return existing  # No insertion, update or publication rollback.
                current = session.get(CurrentPublication, "product-batch")
                if current is not None:
                    previous = session.get(MappingRun, current.mapping_run_id)
                    if (
                        current.source_namespace != namespace
                        or snapshot_date < current.snapshot_date
                        or exported_at < current.sai_exported_at
                    ):
                        raise MappingError(
                            "Older inputs or a different namespace cannot replace the current publication."
                        )
                    same_day_change = (
                        snapshot_date == current.snapshot_date
                        and snapshot.id != previous.snapshot_run_id
                    )
                    if same_day_change and not allow_same_day_correction:
                        raise MappingError(
                            "Same-day snapshot correction requires explicit selection."
                        )
                run = existing or MappingRun(
                    input_key=input_key,
                    snapshot_run_id=snapshot.id,
                    sai_run_id=sai.id,
                    source_namespace=namespace,
                    mapping_version=mapping_version,
                    attempt_count=0,
                )
                run.status, run.started_at, run.completed_at = "running", utcnow(), None
                run.failure_message = None
                run.attempt_count += 1
                session.add(run)
                session.flush()
                run_id = run.id
                session.commit()  # Failed mapping attempts survive publication rollback.
                data = {
                    "products": source_rows(session, snapshot.id, "Products"),
                    "batches": source_rows(session, snapshot.id, "Batches"),
                    "holders": source_rows(session, sai.id, "SAI_ADRESSEN"),
                    "preparations": source_rows(session, sai.id, "SAI_PRAEPARATE"),
                    "packages": source_rows(session, sai.id, "SAI_PACKUNGEN"),
                }
                stats = _map(session, run, data)
                publication = session.get(
                    CurrentPublication, "product-batch"
                ) or CurrentPublication(name="product-batch")
                publication.mapping_run_id, publication.source_namespace = (
                    run.id,
                    namespace,
                )
                publication.snapshot_date, publication.sai_exported_at = (
                    snapshot_date,
                    exported_at,
                )
                publication.published_at = utcnow()
                session.add(publication)
                run.status, run.completed_at, run.statistics = (
                    "succeeded",
                    utcnow(),
                    stats,
                )
                session.commit()
                session.expunge(run)
                return run
            except Exception:  # noqa: BLE001 - no source values, credentials or SQL parameters in failures
                session.rollback()
                if run_id is not None:
                    persisted = session.get(MappingRun, run_id)
                    if persisted is not None and persisted.status == "succeeded":
                        session.expunge(persisted)
                        return (
                            persisted  # Server committed but acknowledgement was lost.
                        )
                    if persisted is not None:
                        persisted.status, persisted.completed_at = "failed", utcnow()
                        persisted.failure_message = "Mapping validation or publication failed; previous publication retained."
                        session.commit()
                raise MappingError(
                    "Mapping failed; inspect source completeness, keys and publication selection."
                ) from None


def _map(session, run, data):
    namespace = run.source_namespace
    unique_rows(data["products"], lambda r: source_key(namespace, r))
    unique_rows(
        data["batches"],
        lambda r: key(source_key(namespace, r), required(r, "Batch Id")),
    )
    unique_rows(data["holders"], lambda r: required(r, "PARTNER_NR"))
    unique_rows(data["preparations"], lambda r: required(r, "ZULASSUNGSNUMMER"))
    unique_rows(
        data["packages"],
        lambda r: (
            required(r, "ZULASSUNGSNUMMER"),
            required(r, "SEQUENZNUMMER"),
            required(r, "PACKUNGSCODE"),
        ),
    )
    # Mark disappearance as not observed; preserve stable IDs and last known values.
    for model in (SAIHolder, SAIPreparation, SAIPackage):
        session.execute(update(model).values(is_observed=0))
    session.execute(
        update(ProductSourceRecord)
        .where(ProductSourceRecord.source_namespace == namespace)
        .values(is_observed=0)
    )
    source_subquery = select(ProductSourceRecord.id).where(
        ProductSourceRecord.source_namespace == namespace
    )
    session.execute(
        update(Batch)
        .where(Batch.product_source_id.in_(source_subquery))
        .values(is_observed=0)
    )
    common = {"last_mapping_run_id": run.id, "is_observed": 1}
    holders = [
        {
            **common,
            "holder_key": key("SAI", required(r, "PARTNER_NR")),
            "partner_number": r["PARTNER_NR"],
            "company_name": r.get("FIRMENNAME"),
            "gln": r.get("GLN_REFDATA"),
            "source_row_id": rid,
            "evidence": selected(r, ("PARTNER_NR", "FIRMENNAME", "GLN_REFDATA")),
        }
        for rid, r in data["holders"]
    ]
    upsert(session, SAIHolder, holders, ["holder_key"])
    holder_ids = ids(session, SAIHolder, "holder_key")
    preparations = []
    current_holders = {r["PARTNER_NR"] for _, r in data["holders"]}
    for rid, r in data["preparations"]:
        holder = r.get("ZULASSUNGSINHABERIN")
        holder_id = holder_ids.get(key("SAI", holder)) if holder else None
        if holder and (not holder_id or holder not in current_holders):
            raise MappingError("SAI preparation references a missing holder.")
        preparations.append(
            {
                **common,
                "preparation_key": key("SAI", required(r, "ZULASSUNGSNUMMER")),
                "approval_number": r["ZULASSUNGSNUMMER"],
                "preparation_name": r.get("PRAEPARATENAME"),
                "holder_id": holder_id,
                "atc_code": r.get("ATC_CODE"),
                "approval_status": r.get("ZULASSUNGSSTATUS"),
                "source_row_id": rid,
                "evidence": selected(
                    r,
                    (
                        "ZULASSUNGSNUMMER",
                        "PRAEPARATENAME",
                        "ZULASSUNGSINHABERIN",
                        "ATC_CODE",
                        "ZULASSUNGSSTATUS",
                    ),
                ),
            }
        )
    upsert(session, SAIPreparation, preparations, ["preparation_key"])
    prep_ids = ids(session, SAIPreparation, "preparation_key")
    current_preps = {r["ZULASSUNGSNUMMER"] for _, r in data["preparations"]}
    packages, gtin_packages = [], defaultdict(list)
    for rid, r in data["packages"]:
        approval, seq, code = (
            required(r, n)
            for n in ("ZULASSUNGSNUMMER", "SEQUENZNUMMER", "PACKUNGSCODE")
        )
        if approval not in current_preps:
            raise MappingError("SAI package references a missing preparation.")
        package_key = key("SAI", approval, seq, code)
        normalized = gtin(r.get("GTIN_INDUSTRY"))
        if normalized:
            gtin_packages[normalized].append(package_key)
        packages.append(
            {
                **common,
                "package_key": package_key,
                "preparation_id": prep_ids[key("SAI", approval)],
                "sequence_number": seq,
                "package_code": code,
                "source_gtin": r.get("GTIN_INDUSTRY"),
                "gtin14": normalized,
                "description_de": r.get("BESCHREIBUNG_DE_REFDATA"),
                "description_fr": r.get("BESCHREIBUNG_FR_REFDATA"),
                "approval_status": r.get("ZULASSUNGSSTATUS"),
                "source_row_id": rid,
                "evidence": selected(
                    r,
                    (
                        "ZULASSUNGSNUMMER",
                        "SEQUENZNUMMER",
                        "PACKUNGSCODE",
                        "GTIN_INDUSTRY",
                        "BESCHREIBUNG_DE_REFDATA",
                        "BESCHREIBUNG_FR_REFDATA",
                        "ZULASSUNGSSTATUS",
                        "IM_HANDEL_DATUM_INDUSTRY",
                        "AUSSER_HANDEL_DATUM_INDUSTRY",
                    ),
                ),
            }
        )
    upsert(session, SAIPackage, packages, ["package_key"])
    package_ids = ids(session, SAIPackage, "package_key")
    products, identity_by_source = {}, {}
    for _, r in data["products"]:
        sk = source_key(namespace, r)
        normalized = (
            gtin(r["Product Code"]) if r["Product Code Scheme"] == "GTIN" else None
        )
        identity = key("GTIN", normalized) if normalized else key("SOURCE", sk)
        identity_by_source[sk] = identity
        products[identity] = {
            "identity_key": identity,
            "gtin14": normalized,
            "first_observed_at": utcnow(),
        }
    upsert(
        session,
        Product,
        list(products.values()),
        ["identity_key"],
        preserve=("first_observed_at",),
    )
    product_ids = ids(session, Product, "identity_key")
    source_records = []
    for rid, r in data["products"]:
        sk = source_key(namespace, r)
        source_records.append(
            {
                **common,
                "source_key": sk,
                "product_id": product_ids[identity_by_source[sk]],
                "source_namespace": namespace,
                "code_scheme": r["Product Code Scheme"],
                "source_code": r["Product Code"],
                "reported_version": source_version(r.get("Product Version Number"))[1],
                "reported_version_text": source_version(
                    r.get("Product Version Number")
                )[0],
                "product_state": r.get("Product State"),
                "pack_count": integer(r.get("Number Of Packs")),
                "active_pack_count": integer(r.get("Number Of Active Packs")),
                "source_row_id": rid,
                "evidence": selected(
                    r,
                    (
                        "Product Code Scheme",
                        "Product Code",
                        "Product Version Number",
                        "Product Name",
                        "MAH Name",
                        "EMVS MAH Id",
                        "OBP Id",
                        "OBP Name",
                        "Product State",
                        "Number Of Packs",
                        "Number Of Active Packs",
                    ),
                ),
            }
        )
    upsert(session, ProductSourceRecord, source_records, ["source_key"])
    source_ids = ids(session, ProductSourceRecord, "source_key")
    versions, current_keys = {}, set(identity_by_source)
    for rid, r in data["products"]:
        sk = source_key(namespace, r)
        raw_version, version = source_version(r.get("Product Version Number"))
        vk = version_identity(sk, raw_version)
        versions[vk] = {
            "version_key": vk,
            "product_source_id": source_ids[sk],
            "version_number": version,
            "source_version_value": raw_version,
            "detail_status": "pmd_observed"
            if version is not None
            else "unresolved_source_value",
            "source_row_id": rid,
            "evidence": selected(
                r,
                (
                    "Product Code Scheme",
                    "Product Code",
                    "Product Version Number",
                    "Product Name",
                    "MAH Name",
                    "EMVS MAH Id",
                    "OBP Id",
                    "OBP Name",
                    "Product State",
                ),
            ),
            "last_mapping_run_id": run.id,
        }
    pmd_keys = set(versions)
    for rid, r in data["batches"]:
        sk = source_key(namespace, r)
        if sk not in current_keys:
            raise MappingError(
                "Batch references a Product absent from the selected snapshot."
            )
        raw_version, version = source_version(r.get("Product Version Number"))
        vk = version_identity(sk, raw_version)
        versions.setdefault(
            vk,
            {
                "version_key": vk,
                "product_source_id": source_ids[sk],
                "version_number": version,
                "source_version_value": raw_version,
                "detail_status": "batch_reference_only"
                if version is not None
                else "unresolved_source_value",
                "source_row_id": rid,
                "evidence": selected(
                    r,
                    (
                        "Product Code Scheme",
                        "Product Code",
                        "Product Version Number",
                        "Batch Id",
                    ),
                ),
                "last_mapping_run_id": run.id,
            },
        )
    existing_versions = ids(session, ProductVersion, "version_key")
    upsert(
        session,
        ProductVersion,
        [v for k, v in versions.items() if k in pmd_keys or k not in existing_versions],
        ["version_key"],
    )
    version_ids = ids(session, ProductVersion, "version_key")
    batches = []
    for rid, r in data["batches"]:
        sk = source_key(namespace, r)
        raw_version, version = source_version(r.get("Product Version Number"))
        batches.append(
            {
                **common,
                "batch_key": key(sk, required(r, "Batch Id")),
                "product_source_id": source_ids[sk],
                "product_version_id": version_ids[version_identity(sk, raw_version)],
                "batch_code": r["Batch Id"],
                "expiry_source_text": r.get("Batch Expiry Date"),
                "batch_state": r.get("Batch State"),
                "pack_count": integer(r.get("Number Of Packs")),
                "active_pack_count": integer(r.get("Number Of Active Packs")),
                "source_row_id": rid,
                "evidence": selected(
                    r,
                    (
                        "Product Code Scheme",
                        "Product Code",
                        "Batch Id",
                        "Product Version Number",
                        "Batch Expiry Date",
                        "Batch State",
                        "Number Of Packs",
                        "Number Of Active Packs",
                        "Manufacturer Name",
                    ),
                ),
            }
        )
    upsert(session, Batch, batches, ["batch_key"])
    matches, statuses = [], defaultdict(int)
    for identity, product in products.items():
        candidates = gtin_packages.get(product["gtin14"], [])
        status = (
            "not_gtin_matchable"
            if not product["gtin14"]
            else "no_sai_match"
            if not candidates
            else "matched_sai"
            if len(candidates) == 1
            else "ambiguous"
        )
        statuses[status] += 1
        matches.append(
            {
                "product_id": product_ids[identity],
                "sai_package_id": package_ids[candidates[0]]
                if len(candidates) == 1
                else None,
                "match_status": status,
                "match_reason": {
                    "matched_sai": "exact_validated_gtin14",
                    "no_sai_match": "absent_from_selected_sai",
                    "not_gtin_matchable": "missing_invalid_or_non_gtin",
                    "ambiguous": "multiple_sai_candidates",
                }[status],
                "last_mapping_run_id": run.id,
            }
        )
    upsert(session, ProductReferenceMatch, matches, ["product_id"])
    return {
        "products": len(products),
        "product_source_records": len(source_records),
        "batches": len(batches),
        "observed_product_versions": len(versions),
        "sai_packages": len(packages),
        "sai_preparations": len(preparations),
        "sai_holders": len(holders),
        "matches": dict(statuses),
        "unresolved_product_version_rows": sum(
            source_version(r.get("Product Version Number"))[1] is None
            for _, r in data["products"]
        ),
        "unresolved_batch_version_rows": sum(
            source_version(r.get("Product Version Number"))[1] is None
            for _, r in data["batches"]
        ),
    }
