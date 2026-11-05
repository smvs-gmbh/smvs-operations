from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import delete, select

from app.core.db.models import ImportMutex
from app.core.db.session import require_runtime_session
from app.domain.mapping import MappingError, canonical, key, source_rows, upsert
from app.domain.models import (
    ActivityDay,
    ActivityFact,
    ActivityPublication,
    LocalOrganisation,
)
from app.integration.artifacts.storage import utcnow
from app.integration.sources.nmvs.activity.parsing import SHEETS
from app.integration.sources.nmvs.activity.processing import PARSER_VERSION

MUTEX = "mapping:activity"
VERSION = "activity-facts-1"
SSR_NAME = "SSR Synthetic Wholesaler PRD (CH)"


def publish_activity(factory, processing_id, namespace):
    if not namespace or len(namespace) > 255:
        raise MappingError("Activity source namespace required.")
    with factory() as lock:
        require_runtime_session(lock)
        lock.execute(
            select(ImportMutex.import_key)
            .where(ImportMutex.import_key == MUTEX)
            .with_for_update()
        ).scalar_one()
        with factory() as session:
            require_runtime_session(session)
            run, artifact = canonical(
                session, processing_id, "NMVS", "UserActivityReport"
            )
            if run.parser_version != PARSER_VERSION:
                raise MappingError("Unsupported activity parser version.")
            origin = urlsplit(artifact.source_uri or "")
            if namespace != f"nmvs-origin:{origin.scheme}://{origin.netloc}":
                raise MappingError(
                    "Activity namespace differs from acquisition origin."
                )
            input_key = key(namespace, run.id, VERSION)
            prior = session.scalar(
                select(ActivityPublication).where(
                    ActivityPublication.input_key == input_key
                )
            )
            if prior:
                session.expunge(prior)
                return prior
            meta = run.file_metadata or {}
            # Exact source-observed values, verified from the actual filtered report.
            if (
                meta.get("Synthetic Monitoring") != "False"
                or meta.get("Activity Days Only") != "False"
            ):
                raise MappingError(
                    "Activity requires genuine transactions and all requested days."
                )
            for field in (
                "Business Processes",
                "Reports",
                "Organisation Types",
                "Organisation ID",
                "IMT Market",
                "Location ID",
                "Client ID/Username",
            ):
                if meta.get(field) != "-":
                    raise MappingError(
                        "Filtered activity report cannot establish national day coverage."
                    )
            from datetime import date

            start, end = (
                date.fromisoformat(meta[k])
                for k in ("Start Date (UTC)", "End Date (UTC)")
            )
            job = artifact.integration_job
            if (
                not job.from_date
                or not job.to_date
                or (job.from_date.date(), job.to_date.date()) != (start, end)
            ):
                raise MappingError(
                    "Activity acquisition period differs from workbook period."
                )
            requested = datetime.fromisoformat(
                meta["Date Requested (UTC)"].replace("Z", "+00:00")
            )
            if requested.tzinfo is None:
                raise MappingError("Source report request time requires a UTC offset.")
            requested = requested.astimezone(UTC).replace(tzinfo=None)
            if end >= datetime.now(UTC).date():
                raise MappingError("Incomplete UTC activity day.")
            old_days = session.scalars(
                select(ActivityDay).where(
                    ActivityDay.source_namespace == namespace,
                    ActivityDay.activity_date.between(start, end),
                )
            ).all()
            for old in old_days:
                previous = session.get(ActivityPublication, old.publication_id)
                if requested <= previous.source_requested_at:
                    raise MappingError(
                        "Older or ambiguous report cannot overwrite accepted activity."
                    )
            pub = ActivityPublication(
                input_key=input_key,
                processing_run_id=run.id,
                source_namespace=namespace,
                mapping_version=VERSION,
                period_start=start,
                period_end=end,
                source_requested_at=requested,
                published_at=utcnow(),
                statistics={},
            )
            session.add(pub)
            session.flush()
            synthetic_ids = set(
                session.scalars(
                    select(LocalOrganisation.source_organisation_id).where(
                        LocalOrganisation.source_namespace == namespace,
                        LocalOrganisation.organisation_name == SSR_NAME,
                    )
                )
            )
            stats = {}
            for section in SHEETS:
                rows = source_rows(session, run.id, section)
                facts = []
                excluded = 0
                for rid, row in rows:
                    if section == "Verification" and (
                        row["Organisation ID"] in synthetic_ids
                        or row["Organisation Name"] == SSR_NAME
                    ):
                        excluded += 1
                        continue
                    day = date.fromisoformat(row["Activity Date"])
                    if not start <= day <= end:
                        raise MappingError("Activity row outside report period.")
                    subject = row.get("Organisation ID", row.get("Market"))
                    facts.append(
                        {
                            "fact_key": key(
                                namespace,
                                section,
                                day.isoformat(),
                                subject,
                                row["Business Process"],
                            ),
                            "source_namespace": namespace,
                            "section": section,
                            "activity_date": day,
                            "source_organisation_id": row.get("Organisation ID"),
                            "organisation_name": row.get("Organisation Name"),
                            "organisation_type": row["Organisation Type"],
                            "market": row.get("Market"),
                            "business_process": row["Business Process"],
                            "metric_kind": row["Metric Kind"],
                            "metric_value": row["Count"],
                            "transaction_count": row["Count"]
                            if row["Metric Kind"] == "transactions"
                            else 0,
                            "exception_count": row["Exceptions Count"],
                            "publication_id": pub.id,
                            "source_row_id": rid,
                            "evidence": dict(row),
                        }
                    )
                if len({f["fact_key"] for f in facts}) != len(facts):
                    raise MappingError("Duplicate daily activity fact.")
                # Complete-day replacement removes observations absent from a corrected report.
                # Prior original bytes and processing/staging runs remain retained.
                upsert(session, ActivityFact, facts, ["fact_key"])
                session.execute(
                    delete(ActivityFact).where(
                        ActivityFact.source_namespace == namespace,
                        ActivityFact.section == section,
                        ActivityFact.activity_date.between(start, end),
                        ActivityFact.publication_id != pub.id,
                    )
                )
                days = [
                    start + timedelta(days=i) for i in range((end - start).days + 1)
                ]
                upsert(
                    session,
                    ActivityDay,
                    [
                        {
                            "day_key": key(namespace, section, d.isoformat()),
                            "source_namespace": namespace,
                            "section": section,
                            "activity_date": d,
                            "publication_id": pub.id,
                        }
                        for d in days
                    ],
                    ["day_key"],
                )
                stats[section] = {
                    "rows": len(facts),
                    "excluded_rows": excluded,
                    "days": len(days),
                }
            pub.statistics = stats
            session.commit()
            session.expunge(pub)
            return pub
