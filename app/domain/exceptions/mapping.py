from urllib.parse import urlsplit

from sqlalchemy import select

from app.core.db.models import ImportMutex
from app.core.db.session import require_runtime_session
from app.domain.mapping import MappingError, canonical, key, source_rows
from app.domain.models import ExceptionPublication, ExceptionRevision, NMVSException
from app.integration.artifacts.storage import utcnow
from app.integration.sources.nmvs.exceptions.parsing import source_time
from app.integration.sources.nmvs.exceptions.processing import PARSER_VERSION
from app.integration.sources.nmvs.parsing import record_hash
from app.integration.sources.sai.parsing import normalize_gtin14

MUTEX = "mapping:exceptions"
VERSION = "exceptions-1"


def optional(row, field, limit=100):
    value = row.get(field)
    if value is None:
        return None
    if (
        field == "organisationID"
        and isinstance(value, int)
        and not isinstance(value, bool)
    ):
        value = str(value)
    if not isinstance(value, str) or len(value) > limit:
        raise MappingError("Invalid exception field type or length.")
    return value


def publish_exceptions(factory, processing_id, namespace):
    if not namespace or len(namespace) > 255:
        raise MappingError("Exception namespace required.")
    with factory() as lock:
        require_runtime_session(lock)
        lock.execute(
            select(ImportMutex.import_key)
            .where(ImportMutex.import_key == MUTEX)
            .with_for_update()
        ).scalar_one()
        with factory() as session:
            run, artifact = canonical(session, processing_id, "NMVS", "ExceptionsQuery")
            if (
                run.parser_version != PARSER_VERSION
                or artifact.channel_name != "Exceptions API"
            ):
                raise MappingError(
                    "Unexpected exception processing version or channel."
                )
            authority = artifact.report_metadata.get("authority")
            # Exception API has a different host from Reporting; explicit source-authority mapping is required.
            if authority != namespace:
                raise MappingError(
                    "Exception acquisition authority does not match publication namespace."
                )
            origin = urlsplit(artifact.source_uri or "")
            if origin.scheme != "https" or not origin.netloc:
                raise MappingError("Exception acquisition origin unavailable.")
            input_key = key(namespace, run.id, VERSION)
            prior = session.scalar(
                select(ExceptionPublication).where(
                    ExceptionPublication.input_key == input_key
                )
            )
            if prior:
                session.expunge(prior)
                return prior
            job = artifact.integration_job
            if not job.from_date or not job.to_date or not job.started_at:
                raise MappingError("Exception query interval unavailable.")
            pub = ExceptionPublication(
                input_key=input_key,
                processing_run_id=run.id,
                source_namespace=namespace,
                mapping_version=VERSION,
                period_start=source_time(
                    artifact.report_metadata["filter"]["startTimestamp"]
                )[0],
                period_end=source_time(
                    artifact.report_metadata["filter"]["endTimestamp"]
                )[0],
                query_started_at=job.started_at,
                captured_at=artifact.received_at,
                published_at=utcnow(),
                statistics={},
            )
            session.add(pub)
            session.flush()
            rows = source_rows(session, run.id, "Alerts")
            stats = {
                "observations": len(rows),
                "new_exceptions": 0,
                "new_revisions": 0,
                "updated": 0,
                "unresolved_dates": 0,
            }
            for rid, row in rows:
                alert_key = key(namespace, "alert", row["uniqueAlertID"])
                existing = session.scalar(
                    select(NMVSException).where(NMVSException.alert_key == alert_key)
                )
                digest = record_hash(row)
                at, status = source_time(row.get("alertDateTime"))
                stats["unresolved_dates"] += status != "parsed"
                fields = {
                    local: optional(row, source, limit)
                    for local, source, limit in [
                        ("transaction_id", "transactionID", 100),
                        ("error_code", "errorCode", 100),
                        ("error_message", "errorMessage", 10000),
                        ("product_code_scheme", "productCodeScheme", 100),
                        ("product_code", "productCode", 100),
                        ("serial_number", "serialNumber", 100),
                        ("provided_batch", "providedBatchNumber", 100),
                        ("stored_batch", "storedBatchNumber", 100),
                        ("organisation_id", "organisationID", 100),
                        ("source_location_id", "sourceLocationID", 100),
                        ("last_update_location_id", "packLastUpdateLocationID", 100),
                        ("source_market", "sourceMarket", 100),
                        ("business_process", "sourceBusinessProcess", 255),
                    ]
                }
                fields["gtin14"] = (
                    normalize_gtin14(fields["product_code"])
                    if fields["product_code_scheme"] in ("GTIN", "GS1", "NTIN")
                    else None
                )
                fields.update(
                    alert_at=at,
                    timestamp_status=status,
                    payload_hash=digest,
                    selection_time=job.started_at,
                    last_observed_at=artifact.received_at,
                    last_publication_id=pub.id,
                    source_row_id=rid,
                    evidence=dict(row),
                    is_intermarket=int(row["isIntermarket"])
                    if row.get("isIntermarket") is not None
                    else None,
                )
                if existing is None:
                    existing = NMVSException(
                        alert_key=alert_key,
                        source_namespace=namespace,
                        unique_alert_id=row["uniqueAlertID"],
                        first_observed_at=artifact.received_at,
                        **fields,
                    )
                    session.add(existing)
                    session.flush()
                    stats["new_exceptions"] += 1
                elif job.started_at > existing.selection_time:
                    for k, v in fields.items():
                        setattr(existing, k, v)
                    stats["updated"] += 1
                elif (
                    job.started_at == existing.selection_time
                    and digest != existing.payload_hash
                ):
                    raise MappingError(
                        "Conflicting exception observations at the same query time."
                    )
                revision_key = key(alert_key, digest)
                previous = session.scalar(
                    select(ExceptionRevision.id).where(
                        ExceptionRevision.revision_key == revision_key
                    )
                )
                if previous is None:
                    session.add(
                        ExceptionRevision(
                            revision_key=revision_key,
                            exception_id=existing.id,
                            publication_id=pub.id,
                            observed_at=artifact.received_at,
                            payload_hash=digest,
                            source_row_id=rid,
                            evidence=dict(row),
                        )
                    )
                    stats["new_revisions"] += 1
            pub.statistics = stats
            session.commit()
            session.expunge(pub)
            return pub
