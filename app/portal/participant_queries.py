from sqlalchemy import func, or_, select

from app.core.db.models import StagingDataset, StagingRow
from app.domain.models import (
    LocalLocation,
    LocalOrganisation,
    ParticipantMappingRun,
    ParticipantPublication,
)
from app.portal.queries import paged


def context(session):
    publication = session.get(ParticipantPublication, "participants")
    run = (
        session.get(ParticipantMappingRun, publication.mapping_run_id)
        if publication
        else None
    )
    return {
        "publication": publication,
        "statistics": run.statistics or {} if run else {},
        "participant_section": True,
    }


def organisations_query(publication):
    counts = (
        select(LocalLocation.organisation_id, func.count().label("location_count"))
        .where(
            LocalLocation.is_observed == 1,
            LocalLocation.last_participant_run_id == publication.mapping_run_id,
        )
        .group_by(LocalLocation.organisation_id)
        .subquery()
    )
    return (
        select(LocalOrganisation, func.coalesce(counts.c.location_count, 0))
        .outerjoin(counts, counts.c.organisation_id == LocalOrganisation.id)
        .where(
            LocalOrganisation.source_namespace == publication.source_namespace,
            LocalOrganisation.is_observed == 1,
            LocalOrganisation.last_participant_run_id == publication.mapping_run_id,
        )
    )


def organisations(
    session, publication, *, q="", status="not_deactivated", type_filter="", page=1
):
    statement = organisations_query(publication)
    if q:
        statement = statement.where(
            or_(
                LocalOrganisation.organisation_name.contains(q, autoescape=True),
                LocalOrganisation.source_organisation_id.contains(q, autoescape=True),
            )
        )
    if status == "not_deactivated":
        statement = statement.where(
            or_(
                LocalOrganisation.organisation_status.is_(None),
                LocalOrganisation.organisation_status != "Deactivated",
            )
        )
    elif status:
        statement = statement.where(LocalOrganisation.organisation_status == status)
    if type_filter:
        statement = statement.where(LocalOrganisation.organisation_type == type_filter)
    rows, pagination = paged(
        session,
        statement.order_by(LocalOrganisation.organisation_name, LocalOrganisation.id),
        page,
    )
    return [
        {"organisation": row[0], "location_count": row[1]} for row in rows
    ], pagination


def locations_query(publication):
    return (
        select(LocalLocation, LocalOrganisation)
        .outerjoin(
            LocalOrganisation, LocalLocation.organisation_id == LocalOrganisation.id
        )
        .where(
            LocalLocation.source_namespace == publication.source_namespace,
            LocalLocation.is_observed == 1,
            LocalLocation.last_participant_run_id == publication.mapping_run_id,
        )
    )


def locations(session, publication, *, q="", status="", organisation_id=None, page=1):
    statement = locations_query(publication)
    if organisation_id is not None:
        statement = statement.where(LocalLocation.organisation_id == organisation_id)
    if q:
        statement = statement.where(
            or_(
                *(
                    field.contains(q, autoescape=True)
                    for field in (
                        LocalLocation.location_name,
                        LocalLocation.source_location_id,
                        LocalLocation.source_organisation_id,
                        LocalLocation.city,
                        LocalLocation.postal_code,
                        LocalOrganisation.organisation_name,
                    )
                )
            )
        )
    if status:
        statement = statement.where(LocalLocation.location_status == status)
    rows, pagination = paged(
        session, statement.order_by(LocalLocation.location_name, LocalLocation.id), page
    )
    return [{"location": row[0], "organisation": row[1]} for row in rows], pagination


def original_values(session, record, kind):
    row = (
        session.get(StagingRow, record.source_row_id) if record.source_row_id else None
    )
    raw = row.raw_row_json if row else record.evidence
    headers = (
        session.get(StagingDataset, row.staging_dataset_id).source_headers
        if row
        else list(raw)
    )
    fields = [(name, raw.get(name)) for name in headers]
    fields.extend((name, value) for name, value in raw.items() if name not in headers)
    return {
        "source_fields": fields,
        "source_complete": True,
        "source_available": row is not None,
        "source_kind": kind,
    }
