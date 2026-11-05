from collections import Counter

from sqlalchemy import select, update

from app.core.db.models import ImportMutex
from app.core.db.session import require_runtime_session
from app.domain.mapping import (
    MappingError,
    canonical,
    ids,
    integer,
    key,
    required,
    source_rows,
    unique_rows,
    upsert,
)
from app.domain.models import (
    LocalLocation,
    LocalOrganisation,
    ParticipantMappingRun,
    ParticipantPublication,
)
from app.integration.artifacts.storage import utcnow

MUTEX = "mapping:participants"
MAPPING_VERSION = "snapshot-participants-1"


def publish_participants(
    session_factory, snapshot_id, namespace, *, allow_same_day_correction=False
):
    if not namespace or len(namespace) > 255:
        raise MappingError("An explicit source namespace is required.")
    with session_factory() as lock:
        require_runtime_session(lock)
        lock.execute(
            select(ImportMutex.import_key)
            .where(ImportMutex.import_key == MUTEX)
            .with_for_update()
        ).scalar_one()
        with session_factory() as session:
            require_runtime_session(session)
            run_id = None
            try:
                snapshot, artifact = canonical(
                    session, snapshot_id, "NMVS", "DailySnapshot"
                )
                snapshot_date = artifact.integration_job.requested_snapshot_date
                if snapshot_date is None:
                    raise MappingError("Snapshot day is unavailable.")
                input_key = key(namespace, snapshot.id, MAPPING_VERSION)
                existing = session.scalar(
                    select(ParticipantMappingRun).where(
                        ParticipantMappingRun.input_key == input_key
                    )
                )
                if existing is not None and existing.status == "succeeded":
                    session.expunge(existing)
                    return existing
                current = session.get(ParticipantPublication, "participants")
                if current is not None:
                    previous = session.get(
                        ParticipantMappingRun, current.mapping_run_id
                    )
                    if (
                        current.source_namespace != namespace
                        or snapshot_date < current.snapshot_date
                    ):
                        raise MappingError(
                            "Older inputs or another namespace cannot replace the current publication."
                        )
                    if (
                        snapshot_date == current.snapshot_date
                        and snapshot.id != previous.snapshot_run_id
                        and not allow_same_day_correction
                    ):
                        raise MappingError(
                            "Same-day snapshot correction requires explicit selection."
                        )
                run = existing or ParticipantMappingRun(
                    input_key=input_key,
                    snapshot_run_id=snapshot.id,
                    source_namespace=namespace,
                    mapping_version=MAPPING_VERSION,
                    attempt_count=0,
                )
                run.status, run.started_at, run.completed_at = "running", utcnow(), None
                run.failure_message = None
                run.attempt_count += 1
                session.add(run)
                session.flush()
                run_id = run.id
                session.commit()
                organisations = source_rows(session, snapshot.id, "Organisations")
                locations = source_rows(session, snapshot.id, "Locations")
                stats = map_rows(session, run, organisations, locations)
                publication = session.get(
                    ParticipantPublication, "participants"
                ) or ParticipantPublication(name="participants")
                publication.mapping_run_id, publication.source_namespace = (
                    run.id,
                    namespace,
                )
                publication.snapshot_date, publication.published_at = (
                    snapshot_date,
                    utcnow(),
                )
                session.add(publication)
                run.statistics, run.status, run.completed_at = (
                    stats,
                    "succeeded",
                    utcnow(),
                )
                session.commit()
                session.expunge(run)
                return run
            except Exception:  # noqa: BLE001 - never expose source contact data or SQL parameters
                session.rollback()
                if run_id is not None:
                    saved = session.get(ParticipantMappingRun, run_id)
                    if saved is not None and saved.status == "succeeded":
                        session.expunge(saved)
                        return saved
                    if saved is not None:
                        saved.status, saved.completed_at = "failed", utcnow()
                        saved.failure_message = "Participant validation or publication failed; previous publication retained."
                        session.commit()
                raise MappingError(
                    "Participant mapping failed; check completeness, source keys and publication selection."
                ) from None


def map_rows(session, run, organisations, locations):
    unique_rows(organisations, lambda r: required(r, "Organisation Id"))
    unique_rows(locations, lambda r: required(r, "Location Id"))
    for model in (LocalOrganisation, LocalLocation):
        session.execute(
            update(model)
            .where(model.source_namespace == run.source_namespace)
            .values(is_observed=0)
        )
    common = {
        "source_namespace": run.source_namespace,
        "is_observed": 1,
        "last_participant_run_id": run.id,
    }
    orgs = [
        {
            **common,
            "source_key": key(
                run.source_namespace, "organisation", required(r, "Organisation Id")
            ),
            "source_organisation_id": r["Organisation Id"],
            "organisation_name": r.get("Organisation Name"),
            "organisation_type": r.get("Organisation Type"),
            "organisation_subtype": r.get("Organisation Sub Type"),
            "organisation_status": r.get("Organisation Status"),
            "creation_date_text": r.get("Creation Date"),
            "registration_date_text": r.get("Registration Date"),
            "expiry_date_text": r.get("Expiry Date"),
            "source_row_id": rid,
            "evidence": dict(r),
        }
        for rid, r in organisations
    ]
    upsert(session, LocalOrganisation, orgs, ["source_key"])
    org_ids = ids(session, LocalOrganisation, "source_key")
    current_orgs = {r["Organisation Id"] for _, r in organisations}
    locs = []
    for rid, r in locations:
        source_org = r.get("Organisation Id")
        if source_org and (not isinstance(source_org, str) or len(source_org) > 100):
            raise MappingError("Invalid source Organisation Id.")
        matched = source_org in current_orgs
        locs.append(
            {
                **common,
                "source_key": key(
                    run.source_namespace, "location", required(r, "Location Id")
                ),
                "source_location_id": r["Location Id"],
                "source_organisation_id": source_org,
                "organisation_id": org_ids[
                    key(run.source_namespace, "organisation", source_org)
                ]
                if matched
                else None,
                "organisation_link_status": "matched"
                if matched
                else "organisation_not_in_snapshot"
                if source_org
                else "missing_organisation_id",
                "location_name": r.get("Location Name"),
                "location_status": r.get("Location Status"),
                "address": r.get("Address"),
                "city": r.get("City"),
                "postal_code": r.get("Postal Code"),
                "legitimacy_information": r.get("Legitimacy Information"),
                "equipment_count": integer(r.get("Equipment Count")),
                "creation_date_text": r.get("Creation Date"),
                "source_row_id": rid,
                "evidence": dict(r),
            }
        )
    upsert(session, LocalLocation, locs, ["source_key"])
    return {
        "organisations": len(orgs),
        "locations": len(locs),
        "organisation_statuses": dict(
            Counter(r.get("Organisation Status") or "" for _, r in organisations)
        ),
        "organisation_types": dict(
            Counter(r.get("Organisation Type") or "" for _, r in organisations)
        ),
        "location_statuses": dict(
            Counter(r.get("Location Status") or "" for _, r in locations)
        ),
        "unlinked_locations": sum(
            r["organisation_link_status"] != "matched" for r in locs
        ),
    }
