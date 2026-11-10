from fastapi import APIRouter, HTTPException, Query, Request

from app.domain.models import LocalLocation, LocalOrganisation
from app.portal import participant_queries as queries
from app.portal.record_navigation import filter_query, list_record_navigation
from app.portal.routes import DbSession, templates

router = APIRouter()
EMPTY = {"page": 1, "pages": 1, "total": 0, "first": 0, "last": 0}


def require_current(session, publication, model, identifier):
    record = session.get(model, identifier)
    if (
        not publication
        or not record
        or not record.is_observed
        or record.source_namespace != publication.source_namespace
        or record.last_participant_run_id != publication.mapping_run_id
    ):
        raise HTTPException(404, "Record not found in the current snapshot.")
    return record


@router.get("/organisations", include_in_schema=False)
def organisation_list(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    status: str = Query("not_deactivated", max_length=100),
    type_filter: str = Query("", alias="type", max_length=100),
    page: int = Query(1, ge=1, le=10000),
):
    from app.portal.table_views import prepare
    prepare(request, session, "organisations")
    ctx = queries.context(session)
    rows, pagination = (
        queries.organisations(
            session,
            ctx["publication"],
            q=q,
            status=status,
            type_filter=type_filter,
            page=page, view_request=request,
        )
        if ctx["publication"]
        else ([], EMPTY)
    )
    return templates.TemplateResponse(
        request=request,
        name="organisations.html",
        context={
            **ctx,
            "title": "Organisations",
            "active": "organisations",
            "rows": rows,
            "pagination": pagination,
            "q": q,
            "status": status,
            "type_filter": type_filter,
        },
    )


def organisation_navigation(request, session, publication, identifier, *, suffix=""):
    return list_record_navigation(
        session,
        queries.organisation_statement(
            publication,
            q=request.query_params.get("q", ""),
            status=request.query_params.get("status", "not_deactivated"),
            type_filter=request.query_params.get("type", ""),
        ),
        LocalOrganisation.id,
        identifier,
        queries.ORGANISATION_ORDER,
        "/organisations",
        "Organisations",
        view_request=request, table_key="organisations",
        suffix=suffix,
        query=filter_query(request, "q", "status", "type"),
    )


@router.get("/organisations/{organisation_id}", include_in_schema=False)
def organisation_detail(
    request: Request,
    organisation_id: int,
    session: DbSession,
    page: int = Query(1, ge=1, le=10000),
):
    from app.portal.table_views import prepare
    prepare(request, session, "organisation-locations")
    ctx = queries.context(session)
    org = require_current(
        session, ctx["publication"], LocalOrganisation, organisation_id
    )
    rows, pagination = queries.locations(
        session, ctx["publication"], organisation_id=org.id, page=page, view_request=request, table_key="organisation-locations"
    )
    return templates.TemplateResponse(
        request=request,
        name="organisation_detail.html",
        context={
            **ctx,
            "title": org.organisation_name or org.source_organisation_id,
            "active": "organisations",
            "organisation": org,
            "record_nav": organisation_navigation(
                request, session, ctx["publication"], org.id
            ),
            "rows": rows,
            "pagination": pagination,
        },
    )


@router.get("/organisations/{organisation_id}/source", include_in_schema=False)
def organisation_source(request: Request, organisation_id: int, session: DbSession):
    ctx = queries.context(session)
    org = require_current(
        session, ctx["publication"], LocalOrganisation, organisation_id
    )
    return templates.TemplateResponse(
        request=request,
        name="source.html",
        context={
            **ctx,
            **queries.original_values(session, org, "Organisations"),
            "title": "NMVS Organisations · Original data",
            "active": "organisations",
            "product": {"source_code": org.source_organisation_id, "gtin14": None},
            "record_nav": organisation_navigation(
                request, session, ctx["publication"], org.id, suffix="/source"
            ),
            "back_url": f"/organisations/{org.id}",
            "back_label": "Organisation details",
        },
    )


@router.get("/locations", include_in_schema=False)
def location_list(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    status: str = Query("", max_length=100),
    page: int = Query(1, ge=1, le=10000),
):
    from app.portal.table_views import prepare
    prepare(request, session, "locations")
    ctx = queries.context(session)
    rows, pagination = (
        queries.locations(session, ctx["publication"], q=q, status=status, page=page, view_request=request)
        if ctx["publication"]
        else ([], EMPTY)
    )
    return templates.TemplateResponse(
        request=request,
        name="locations.html",
        context={
            **ctx,
            "title": "Locations",
            "active": "locations",
            "rows": rows,
            "pagination": pagination,
            "q": q,
            "status": status,
        },
    )


def location_navigation(
    request, session, publication, identifier, organisation_id, *, suffix=""
):
    related = organisation_id and request.query_params.get("related") == "true"
    return list_record_navigation(
        session,
        queries.location_statement(
            publication,
            q=request.query_params.get("q", ""),
            status=request.query_params.get("status", ""),
            organisation_id=organisation_id if related else None,
        ),
        LocalLocation.id,
        identifier,
        queries.LOCATION_ORDER,
        "/locations",
        "Organisation and related locations" if related else "Locations",
        view_request=request, table_key="organisation-locations" if related else "locations",
        suffix=suffix,
        query=filter_query(request, "q", "status", "related"),
        back_path=f"/organisations/{organisation_id}" if related else None,
        back_query=filter_query(request) if related else None,
    )


@router.get("/locations/{location_id}", include_in_schema=False)
def location_detail(request: Request, location_id: int, session: DbSession):
    ctx = queries.context(session)
    location = require_current(session, ctx["publication"], LocalLocation, location_id)
    org = (
        session.get(LocalOrganisation, location.organisation_id)
        if location.organisation_id
        else None
    )
    return templates.TemplateResponse(
        request=request,
        name="location_detail.html",
        context={
            **ctx,
            "title": location.location_name or location.source_location_id,
            "active": "locations",
            "location": location,
            "record_nav": location_navigation(
                request,
                session,
                ctx["publication"],
                location.id,
                location.organisation_id,
            ),
            "organisation": org,
        },
    )


@router.get("/locations/{location_id}/source", include_in_schema=False)
def location_source(request: Request, location_id: int, session: DbSession):
    ctx = queries.context(session)
    location = require_current(session, ctx["publication"], LocalLocation, location_id)
    return templates.TemplateResponse(
        request=request,
        name="source.html",
        context={
            **ctx,
            **queries.original_values(session, location, "Locations"),
            "title": "NMVS Locations · Original data",
            "active": "locations",
            "product": {"source_code": location.source_location_id, "gtin14": None},
            "record_nav": location_navigation(
                request,
                session,
                ctx["publication"],
                location.id,
                location.organisation_id,
                suffix="/source",
            ),
            "back_url": f"/locations/{location.id}",
            "back_label": "Location details",
        },
    )
