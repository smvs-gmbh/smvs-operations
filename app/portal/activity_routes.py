from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request

from app.domain.models import LocalOrganisation
from app.portal.activity_queries import activity, namespace
from app.portal.routes import DbSession, templates

router = APIRouter()


def render(
    request,
    session,
    section,
    *,
    start,
    end,
    days,
    organisation,
    market,
    process,
    org_type,
    sort,
    day,
    org_record=None,
):
    if section not in ("verification", "imt"):
        raise HTTPException(404, "Activity view not found.")
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    end = end or yesterday
    start = start or end - timedelta(days=days - 1)
    if (
        end < start
        or (end - start).days > 365
        or end > yesterday
        or day
        and not start <= day <= end
    ):
        raise HTTPException(
            422,
            "Select a period of at most 366 complete UTC days.",
        )
    if section == "imt" and (organisation or org_type):
        raise HTTPException(422, "IMT is analysed by market.")
    if section == "verification" and market:
        raise HTTPException(422, "Verification is analysed by organisation.")
    ctx = activity(
        session,
        section="Verification" if section == "verification" else "IMT Fulfilment",
        start=start,
        end=end,
        organisation=organisation,
        market=market,
        process=process,
        org_type=org_type,
        sort=sort,
        day=day,
    )
    return templates.TemplateResponse(
        request=request,
        name="activity.html",
        context={
            **ctx,
            "title": "Activity",
            "active": "activity",
            "section": section,
            "start": start,
            "end": end,
            "organisation": organisation,
            "market": market,
            "process": process,
            "org_type": org_type,
            "sort": sort,
            "day": day,
            "org_record": org_record,
        },
    )


@router.get("/activity/{section}", include_in_schema=False)
def overview(
    request: Request,
    session: DbSession,
    section: str,
    start: date | None = None,
    end: date | None = None,
    days: int = Query(30, ge=1, le=366),
    organisation: str = Query("", max_length=100),
    market: str = Query("", max_length=100),
    process: str = Query("", max_length=255),
    org_type: str = Query("", max_length=100),
    sort: str = Query("count", pattern="^(count|exceptions|name|rate|delta)$"),
    day: date | None = None,
):
    return render(
        request,
        session,
        section,
        start=start,
        end=end,
        days=days,
        organisation=organisation,
        market=market,
        process=process,
        org_type=org_type,
        sort=sort,
        day=day,
    )


@router.get("/organisations/{organisation_id}/activity", include_in_schema=False)
def organisation_activity(
    request: Request,
    session: DbSession,
    organisation_id: int,
    start: date | None = None,
    end: date | None = None,
    days: int = Query(30, ge=1, le=366),
    process: str = Query("", max_length=255),
    sort: str = Query("count", pattern="^(count|exceptions|name|rate|delta)$"),
    day: date | None = None,
):
    org = session.get(LocalOrganisation, organisation_id)
    if not org or org.source_namespace != namespace(session):
        raise HTTPException(404, "Organisation not found.")
    return render(
        request,
        session,
        "verification",
        start=start,
        end=end,
        days=days,
        organisation=org.source_organisation_id,
        market="",
        process=process,
        org_type="",
        sort=sort,
        day=day,
        org_record=org,
    )
