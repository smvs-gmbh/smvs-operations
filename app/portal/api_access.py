"""Read-only API access observations from one successful NMVS snapshot delivery."""

from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, case, func, or_, select

from app.core.db.models import (
    AcquiredArtifact,
    IntegrationJob,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.domain.models import (
    LocalLocation,
    LocalOrganisation,
    ParticipantMappingRun,
    ParticipantPublication,
)
from app.portal.queries import paged
from app.portal.routes import DbSession, templates

router = APIRouter()
SERVICES = {
    name + " API Versions": name + " API"
    for name in (
        "Verification",
        "Authentication",
        "Identity",
        "Reporting",
        "NMVO Exception",
    )
}
HEADERS = [
    "Organisation Name",
    "Organisation Id",
    "Organisation Type",
    "Location Id",
    "Client Id",
    "User-Agent",
    "IP Address",
    "Last API Request",
]


def value(header):
    return StagingRow.raw_row_json[header].as_string()


def sql_fields():
    return [
        *((value(h), "text") for h in HEADERS),
        (case(SERVICES, value=StagingDataset.source_dataset_name), "text"),
        (value("API Version"), "text"),
        (value("Requested API Version"), "text"),
        (func.substr(value("Last API Request"), 1, 10), "date"),
        (None, "text"),
    ]


def deliveries():
    return (
        select(
            ProcessingRun.id,
            IntegrationJob.requested_snapshot_date,
            ProcessingRun.completed_at,
        )
        .join(AcquiredArtifact, ProcessingRun.artifact_id == AcquiredArtifact.id)
        .join(IntegrationJob, AcquiredArtifact.integration_job_id == IntegrationJob.id)
        .where(
            ProcessingRun.status == "succeeded",
            AcquiredArtifact.source_name == "NMVS",
            AcquiredArtifact.channel_name == "Reporting API",
            AcquiredArtifact.report_type == "DailySnapshot",
            ProcessingRun.reused_from_run_id.is_(None),
            select(StagingDataset.id)
            .where(StagingDataset.processing_run_id == ProcessingRun.id)
            .exists(),
        )
        .order_by(
            IntegrationJob.requested_snapshot_date.desc(),
            ProcessingRun.completed_at.desc(),
            ProcessingRun.id.desc(),
        )
    )


def snapshot_context(session, identifier=None):
    options = session.execute(deliveries().limit(366)).all()
    selected = (
        session.execute(deliveries().where(ProcessingRun.id == identifier)).first()
        if identifier is not None
        else (options[0] if options else None)
    )
    if identifier is not None and selected is None:
        raise HTTPException(404, "Snapshot delivery not found.")
    if selected and selected not in options:
        options.append(selected)
    datasets = (
        list(
            session.scalars(
                select(StagingDataset)
                .where(
                    StagingDataset.processing_run_id == selected.id,
                    StagingDataset.source_dataset_name.in_(SERVICES),
                )
                .order_by(StagingDataset.section_order)
            )
        )
        if selected
        else []
    )
    return {
        "deliveries": options,
        "delivery": selected,
        "datasets": datasets,
        "missing_services": [
            label
            for name, label in SERVICES.items()
            if name not in {d.source_dataset_name for d in datasets}
        ],
    }


def statement(session, context):
    # Link only to records from this exact published delivery; never join historical
    # observations to another snapshot or infer an affiliation from a matching name.
    publication = session.get(ParticipantPublication, "participants")
    mapping = (
        session.get(ParticipantMappingRun, publication.mapping_run_id)
        if publication
        else None
    )
    same = bool(
        mapping
        and context["delivery"]
        and mapping.snapshot_run_id == context["delivery"].id
    )
    namespace = publication.source_namespace if same else ""
    run_id = publication.mapping_run_id if same else -1
    return (
        select(
            StagingRow,
            StagingDataset.source_dataset_name,
            LocalOrganisation.id.label("organisation_id"),
            LocalLocation.id.label("location_id"),
        )
        .join(StagingDataset, StagingRow.staging_dataset_id == StagingDataset.id)
        .outerjoin(
            LocalOrganisation,
            and_(
                LocalOrganisation.source_namespace == namespace,
                LocalOrganisation.is_observed == 1,
                LocalOrganisation.last_participant_run_id == run_id,
                LocalOrganisation.source_organisation_id == value("Organisation Id"),
            ),
        )
        .outerjoin(
            LocalLocation,
            and_(
                LocalLocation.source_namespace == namespace,
                LocalLocation.is_observed == 1,
                LocalLocation.last_participant_run_id == run_id,
                LocalLocation.source_location_id == value("Location Id"),
                LocalLocation.source_organisation_id == value("Organisation Id"),
            ),
        )
        .where(StagingRow.staging_dataset_id.in_([d.id for d in context["datasets"]]))
    )


@router.get("/api-access", include_in_schema=False)
def api_access(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=500),
    agent: str = Query("", max_length=500),
    ip: str = Query("", max_length=150),
    service: str = Query("", max_length=100),
    snapshot: str = Query("", pattern=r"^(?:[1-9][0-9]{0,17})?$"),
    from_date: str = Query("", pattern=r"^(?:[0-9]{4}-[0-9]{2}-[0-9]{2})?$"),
    to_date: str = Query("", pattern=r"^(?:[0-9]{4}-[0-9]{2}-[0-9]{2})?$"),
    page: int = Query(1, ge=1, le=100000),
):
    from app.portal.table_views import apply_sql, prepare

    prepare(request, session, "api-access")
    if service and service not in SERVICES:
        raise HTTPException(422, "Select a known API service.")
    snapshot = int(snapshot) if snapshot else None
    try:
        from_date = date.fromisoformat(from_date) if from_date else None
        to_date = date.fromisoformat(to_date) if to_date else None
    except ValueError:
        raise HTTPException(422, "Use ISO dates (YYYY-MM-DD).") from None
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "The start date must not follow the end date.")
    context = snapshot_context(session, snapshot)
    if snapshot is None and context["delivery"]:
        params = dict(request.query_params) | {"snapshot": str(context["delivery"].id)}
        return RedirectResponse("/api-access?" + urlencode(params), status_code=303)
    query = statement(session, context)
    if q:
        query = query.where(
            or_(
                *(
                    func.lower(column).contains(q.lower(), autoescape=True)
                    for column, _ in sql_fields()
                    if column is not None
                )
            )
        )
    for text, header in ((agent, "User-Agent"), (ip, "IP Address")):
        if text:
            query = query.where(
                func.lower(value(header)).contains(text.lower(), autoescape=True)
            )
    if service:
        query = query.where(StagingDataset.source_dataset_name == service)
    for bound, comparison in ((from_date, "after"), (to_date, "before")):
        if bound:
            day = func.substr(value("Last API Request"), 1, 10)
            query = query.where(func.length(day) == 10, day.like("____-__-__"))
            query = query.where(
                day >= bound.isoformat()
                if comparison == "after"
                else day <= bound.isoformat()
            )
    query = query.order_by(value("Last API Request").desc(), StagingRow.id)
    # Metrics and rows use the same pre-pagination saved-view conditions.
    filtered = (
        apply_sql(request, session, query, "api-access").order_by(None).subquery()
    )
    metrics = session.execute(
        select(
            func.count(),
            func.count(
                func.distinct(
                    func.nullif(
                        filtered.c.raw_row_json["Organisation Id"].as_string(), ""
                    )
                )
            ),
            func.count(
                func.distinct(
                    func.nullif(filtered.c.raw_row_json["Client Id"].as_string(), "")
                )
            ),
        )
    ).one()
    rows, pagination = paged(
        session, query, page, view_request=request, table_key="api-access"
    )
    return templates.TemplateResponse(
        request=request,
        name="api_access.html",
        context={
            **context,
            "title": "API Access",
            "active": "api_access",
            "services": SERVICES,
            "rows": rows,
            "pagination": pagination,
            "metrics": metrics,
            "q": q,
            "agent": agent,
            "ip": ip,
            "service": service,
            "snapshot": snapshot,
            "from_date": from_date,
            "to_date": to_date,
        },
    )


@router.get("/api-access/{row_id}/source", include_in_schema=False)
def source(request: Request, row_id: int, session: DbSession):
    record = session.get(StagingRow, row_id)
    dataset = session.get(StagingDataset, record.staging_dataset_id) if record else None
    if not dataset or dataset.source_dataset_name not in SERVICES:
        raise HTTPException(404, "API access observation not found.")
    context = snapshot_context(session, dataset.processing_run_id)
    return templates.TemplateResponse(
        request=request,
        name="api_access_source.html",
        context={
            **context,
            "title": "Original API access observation",
            "active": "api_access",
            "back_query": urlencode(
                dict(request.query_params) | {"snapshot": str(context["delivery"].id)}
            ),
            "record": record,
            "dataset": dataset,
        },
    )
