from math import ceil
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select

from app.core.db.models import AcquiredArtifact
from app.core.db.session import SessionFactory
from app.domain.models import PackAuditReport, PackAuditRequest
from app.domain.pack_audit.service import record_signature, request_report
from app.domain.pack_audit.timeline import summarize
from app.integration.sources.nmvs.pack_audit.parsing import details
from app.portal import exception_queries
from app.portal.exception_routes import current, exception_record_navigation
from app.portal.routes import DbSession, templates

router = APIRouter()


def state(session, record):
    try:
        sig = record_signature(record)
    except ValueError:
        return None, None, False
    task = session.scalar(
        select(PackAuditRequest).where(PackAuditRequest.signature_key == sig)
    )
    report = (
        session.get(PackAuditReport, task.latest_report_id)
        if task and task.latest_report_id
        else None
    )
    if report and (
        report.signature_key != sig
        or report.source_namespace != record.source_namespace
        or report.is_example
    ):
        raise HTTPException(
            409, "The report is not unambiguously matched to this pack."
        )
    return task, report, True


def render(
    request,
    session,
    report,
    *,
    record=None,
    task=None,
    eligible=False,
    show="relevant",
    page=1,
):
    anchor = (
        record.unique_alert_id
        if record
        else next(
            (
                details(e.get("Event Details")).get("AlertId")
                for e in report.events_json
                if details(e.get("Event Details")).get("AlertId")
            ),
            None,
        )
        if report
        else None
    )
    result = (
        summarize(
            report.events_json,
            alert_id=anchor,
            transaction_id=record.transaction_id if record else None,
        )
        if report
        else None
    )
    rows = (result["groups"] if show == "all" else result["relevant"]) if result else []
    pages = max(1, ceil(len(rows) / 50))
    page = min(page, pages)
    return templates.TemplateResponse(
        request=request,
        name="pack_audit.html",
        context={
            "record_nav": exception_record_navigation(request, session, record)
            if record
            else None,
            **exception_queries.context(session),
            "pack_audit_section": True,
            "title": "Pack audit trail",
            "active": "exceptions",
            "record": record,
            "task": task,
            "report": report,
            "eligible": eligible,
            "timeline": result,
            "groups": rows[(page - 1) * 50 : page * 50],
            "show": show,
            "page": page,
            "pages": pages,
            "anchor_alert_id": anchor,
            "example": bool(report and report.is_example),
        },
    )


@router.get("/exceptions/{identifier}/audit-trail", include_in_schema=False)
def audit(
    request: Request,
    identifier: int,
    session: DbSession,
    show: str = Query("relevant", pattern="^(relevant|all)$"),
    page: int = Query(1, ge=1, le=10000),
):
    record = current(session, identifier)
    task, report, eligible = state(session, record)
    return render(
        request,
        session,
        report,
        record=record,
        task=task,
        eligible=eligible,
        show=show,
        page=page,
    )


@router.post("/exceptions/{identifier}/audit-trail", include_in_schema=False)
def request_audit(
    request: Request, identifier: int, session: DbSession, refresh: bool = False
):
    # An explicit local same-origin action queues evidence; GET never requests a source report.
    origin = urlsplit(str(request.url))
    if request.headers.get("origin") != f"{origin.scheme}://{origin.netloc}":
        raise HTTPException(403, "Request the report from the local detail view.")
    current(session, identifier)
    try:
        request_report(SessionFactory, identifier, refresh=refresh)
    except ValueError:
        raise HTTPException(
            422,
            "Product code scheme, product code or serial number is missing or unsupported.",
        ) from None
    return RedirectResponse(f"/exceptions/{identifier}/audit-trail", status_code=303)


@router.get("/pack-audit/example", include_in_schema=False)
def example(
    request: Request,
    session: DbSession,
    show: str = Query("relevant", pattern="^(relevant|all)$"),
    page: int = Query(1, ge=1, le=10000),
):
    report = session.scalar(
        select(PackAuditReport)
        .where(PackAuditReport.is_example == 1)
        .order_by(PackAuditReport.id.desc())
        .limit(1)
    )
    if not report:
        raise HTTPException(404, "No example report has been retained yet.")
    return render(request, session, report, show=show, page=page)


@router.get("/pack-audit/reports/{report_id}/original", include_in_schema=False)
def original(report_id: int, session: DbSession):
    report = session.get(PackAuditReport, report_id)
    if (
        not report
        or not report.is_example
        and report.source_namespace != exception_queries.namespace(session)
    ):
        raise HTTPException(404, "Report not found.")
    artifact = session.get(AcquiredArtifact, report.acquired_artifact_id)
    if not artifact:
        raise HTTPException(404, "Original report unavailable.")
    return Response(
        artifact.artifact_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="pack-audit-{report.id}.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
