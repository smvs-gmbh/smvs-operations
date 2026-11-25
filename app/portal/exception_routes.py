from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from starlette.concurrency import run_in_threadpool

from app.alert_desk.schema import CAPA, COMPARISON, FINDINGS
from app.core.config import get_settings
from app.domain.exceptions import causes, repeat_evidence
from app.domain.exceptions import review as work
from app.domain.exceptions.list_search import interpret_filters
from app.domain.investigations import rca, responses
from app.domain.models import ExceptionReview, ExceptionReviewEvent, NMVSException
from app.integration.sources import ams
from app.portal import alert_trends
from app.portal import exception_queries as queries
from app.portal.queries import paged
from app.portal.record_navigation import list_record_navigation
from app.portal.routes import DbSession, templates

router = APIRouter()


@router.get("/exceptions/trends", include_in_schema=False)
def exception_trends(
    request: Request,
    session: DbSession,
    start: date | None = None,
    end: date | None = None,
    alert_group: str = Query("", pattern="^(|a2-a3)$"),
    country: str = Query("", pattern="^(|CH|LI)$"),
):
    today = datetime.now(UTC).date()
    end = end or today
    if start is None:
        year = end.year - (end.month < 12)
        start = date(year, end.month % 12 + 1, 1) if year else date.min
    if end < start or (end - start).days > 366 or end > today:
        raise HTTPException(
            422, "Select a period of at most 367 days ending today or earlier."
        )
    ctx = queries.context(session)
    report = alert_trends.trends(
        session, ctx["source_namespace"], start, end, alert_group, country
    )
    return templates.TemplateResponse(
        request=request,
        name="alert_trends.html",
        context={
            **ctx,
            **report,
            "title": "Alert Trends",
            "active": "exceptions",
            "start": start,
            "end": end,
            "alert_group": alert_group,
            "country": country,
            "days": (end - start).days + 1,
        },
    )


@router.get("/exceptions", include_in_schema=False)
def exception_list(
    request: Request,
    session: DbSession,
    start: date | None = None,
    end: date | None = None,
    q: str = Query("", max_length=150),
    error: str = Query("", max_length=100),
    alert_group: str = Query("", pattern="^(|a2-a3)$"),
    gtin14: str = Query("", pattern="^(|[0-9]{14})$"),
    country: str = Query("", pattern="^(|CH|LI)$"),
    market: str = Query("", max_length=100),
    organisation: str = Query("", max_length=100),
    location: str = Query("", max_length=100),
    process: str = Query("", max_length=255),
    date_quality: str = Query("", pattern="^(|unresolved)$"),
    intermarket: str = Query("", pattern="^(|yes|no|unset)$"),
    work_status: str = Query("open", pattern="^(open|to_do|resolved|all)$"),
    response_status: str = Query(
        "", pattern="^(|awaiting|overdue|received|not_requested)$"
    ),
    response_party: str = Query("", pattern="^(|end_user|mah)$"),
    page: int = Query(1, ge=1, le=10000),
):
    from app.portal.collaboration_routes import pilot_enabled
    from app.portal.table_views import has_exception_response_conditions, prepare

    prepare(request, session, "exceptions")
    all_response_dates = bool(
        response_status or response_party
    ) or has_exception_response_conditions(request, session)
    end = end or datetime.now(UTC).date()
    start = start or end - timedelta(days=29)
    if end < start or (end - start).days > 366 or end == date.max:
        raise HTTPException(422, "Select a period of at most 367 days.")
    if work_status == "to_do":
        date_quality = ""
    ctx = queries.context(session)
    rows, pagination = queries.listing(
        session,
        start=start,
        end=end,
        q=q,
        error=error,
        alert_group=alert_group,
        gtin14=gtin14,
        country=country,
        market=market,
        organisation=organisation,
        location=location,
        process=process,
        date_quality=date_quality,
        intermarket=intermarket,
        page=page,
        view_request=request,
        work_status=work_status,
        response_status=response_status,
        response_party=response_party,
        all_response_dates=all_response_dates,
    )
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="exceptions.html",
        context={
            **ctx,
            **queries.options(session),
            "title": "Exceptions",
            "language_search_enabled": bool(
                settings.openai_api_key and settings.openai_search_model
            ),
            "active": "exceptions",
            "rows": rows,
            "pagination": pagination,
            "record_query": "?"
            + urlencode(
                {
                    "nav_start": start.isoformat(),
                    "nav_end": end.isoformat(),
                    **{
                        key: request.query_params[key]
                        for key in (
                            *EXCEPTION_NAV_FILTERS,
                            *(k for k in request.query_params if k.startswith("tv_")),
                        )
                        if key in request.query_params
                    },
                }
            ),
            "start": start,
            "end": end,
            "q": q,
            "error": error,
            "alert_group": alert_group,
            "gtin14": gtin14,
            "country": country,
            "market": market,
            "organisation_filter": organisation,
            "location_filter": location,
            "process": process,
            "date_quality": date_quality,
            "intermarket": intermarket,
            "work_status": work_status,
            "response_status": response_status,
            "response_party": response_party,
            "response_labels": responses.STATUS_LABELS,
            "all_response_dates": all_response_dates,
            "reminders_available": bool(rca_staff(request)) and pilot_enabled(),
        },
    )


@router.post("/exceptions/search-draft", include_in_schema=False)
async def exception_search_draft(request: Request, session: DbSession):
    settings = get_settings()
    if not settings.openai_api_key or not settings.openai_search_model:
        raise HTTPException(503, "Configure OpenAI search before using language input.")
    question = (await review_form(request)).get("question", "").strip()
    if not question or len(question) > 500:
        raise HTTPException(422, "Enter a search question of up to 500 characters.")
    try:
        draft = await run_in_threadpool(interpret_filters, question, settings)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(
            502,
            "The search question could not be interpreted. Use the filters to continue.",
        ) from None
    filters = {}
    if draft:
        end = datetime.now(UTC).date()
        filters = {
            "start": end - timedelta(days=draft.days - 1),
            "end": end,
            "error": draft.error,
            "market": draft.market,
            "work_status": draft.work_status,
            "q": draft.q,
        }
    return templates.TemplateResponse(
        request=request,
        name="exception_filter_draft.html",
        context={
            **queries.context(session),
            "active": "exceptions",
            "title": "Search draft",
            "filters": filters,
            "target": "/exceptions?" + urlencode(filters),
        },
    )


def current(session, identifier):
    record = session.get(NMVSException, identifier)
    if not record or record.source_namespace != queries.namespace(session):
        raise HTTPException(404, "Exception not found.")
    return record


EXCEPTION_NAV_FILTERS = (
    "q",
    "error",
    "alert_group",
    "gtin14",
    "country",
    "market",
    "organisation",
    "location",
    "process",
    "date_quality",
    "intermarket",
    "work_status",
    "response_status",
    "response_party",
)


def exception_record_navigation(request, session, record):
    from app.portal.table_views import has_exception_response_conditions

    params = request.query_params
    filters = {key: params[key] for key in EXCEPTION_NAV_FILTERS if key in params}
    if filters.get("alert_group", "") not in ("", "a2-a3") or filters.get("country", "") not in ("", "CH", "LI"):
        raise HTTPException(422, "Choose a valid trend filter.")
    if "nav_start" in params or "nav_end" in params:
        try:
            start = date.fromisoformat(params.get("nav_start", ""))
            end = date.fromisoformat(params.get("nav_end", ""))
            if end < start or (end - start).days > 366 or end == date.max:
                raise ValueError()
        except ValueError:
            raise HTTPException(422, "Select a valid exception period.") from None
    else:
        end = record.alert_at.date() if record.alert_at else datetime.now(UTC).date()
        start = end - timedelta(days=29)
        if not filters:
            filters["work_status"] = "all"
            if not record.alert_at:
                filters["date_quality"] = "unresolved"
    if filters.get("work_status") == "to_do":
        filters["date_quality"] = ""
    for name, allowed in (
        ("response_status", responses.STATUS_LABELS),
        ("response_party", rca.ROLES),
    ):
        if filters.get(name) and filters[name] not in allowed:
            raise HTTPException(422, "Choose a valid response filter.")
    all_response_dates = bool(
        filters.get("response_status") or filters.get("response_party")
    ) or has_exception_response_conditions(request, session)
    statement, ordering = queries.listing_statement(
        session, start=start, end=end, all_response_dates=all_response_dates, **filters
    )
    view_params = {k: v for k, v in params.items() if k.startswith("tv_")}
    query = "?" + urlencode(
        {"nav_start": start, "nav_end": end, **filters, **view_params}
    )
    suffix = request.url.path.removeprefix(f"/exceptions/{record.id}")
    navigation = list_record_navigation(
        session,
        statement,
        NMVSException.id,
        record.id,
        ordering,
        "/exceptions",
        "Exceptions",
        view_request=request,
        table_key="exceptions",
        suffix=suffix,
        query=query,
        back_query="?"
        + urlencode({"start": start, "end": end, **filters, **view_params}),
    )
    navigation["query"] = query
    return navigation


def hub_context(request, record, *, load=False):
    if not rca_staff(request) or any(
        getattr(request.app.state, flag, False)
        for flag in ("test_workspace", "alert_desk_test_workspace")
    ):
        return {}
    settings = get_settings()
    if not settings.ams_hub_environment:
        return {}
    return {
        "hub_environment": settings.ams_hub_environment.upper(),
        "hub_investigation": ams.lookup(settings, record.unique_alert_id)
        if load or request.query_params.get("ams") == "1"
        else None,
    }


@router.get("/exceptions/{identifier}", include_in_schema=False)
def exception_detail(request: Request, identifier: int, session: DbSession):
    record = current(session, identifier)
    return templates.TemplateResponse(
        request=request,
        name="exception_detail.html",
        context={
            **queries.context(session),
            **queries.detail(session, record),
            **hub_context(request, record),
            "review": session.get(ExceptionReview, identifier),
            "record_nav": exception_record_navigation(request, session, record),
            "title": record.unique_alert_id,
            "active": "exceptions",
        },
    )


@router.get("/exceptions/{identifier}/ams-hub", include_in_schema=False)
def exception_ams_history(request: Request, identifier: int, session: DbSession):
    if not rca_staff(request):
        raise HTTPException(403, "NMVO access is required.")
    record = current(session, identifier)
    return templates.TemplateResponse(
        request=request,
        name="exception_ams_history.html",
        context={
            **queries.context(session),
            **hub_context(request, record, load=True),
            "record": record,
            "record_nav": exception_record_navigation(request, session, record),
            "title": record.unique_alert_id,
            "active": "exceptions",
            "hub_full_history": True,
        },
    )


@router.get("/exceptions/{identifier}/analysis", include_in_schema=False)
def exception_analysis(request: Request, identifier: int, session: DbSession):
    record = current(session, identifier)
    review = session.get(ExceptionReview, identifier)
    from app.portal.collaboration_routes import pilot_enabled

    can_decide = bool(rca_staff(request))
    scope = rca.responsibility(session, record)
    findings = rca.participant_findings(session, [record.id]) if can_decide else {}
    view = queries.detail(session, record)
    resolved = rca.resolved_for_source(review, record)
    batch_groups = (
        rca.batch_groups(rca.batch_rows(session, record))
        if can_decide and not resolved and scope != "unconfirmed"
        else {}
    )
    batch_finding_links = {}
    test_review = None
    if can_decide and getattr(request.app.state, "alert_desk_test_workspace", False):
        from app.alert_desk.test_workspace import (
            batch_finding_links_for,
            case_id_for_alert,
            individual_review_reasons,
        )

        batch_finding_links = batch_finding_links_for(session, record, findings.get(record.id, {}))
        flags, reasons = individual_review_reasons(session, findings)
        test_review = {
            "case_id": case_id_for_alert(record),
            "flag": flags.get(identifier),
            "reasons": reasons.get(identifier, []),
        }
    response_contacts = {}
    if can_decide and not resolved and scope != "unconfirmed" and pilot_enabled():
        for role in responses.applicable_roles(record):
            crm, _, issue = responses.recipient_scope(session, record, role, view)
            response_contacts[role] = {
                "issue": issue,
                "invitation_url": (
                    f"/workflows/alert-desk?role={role}&organisation_id={crm.id}&case_id={identifier}"
                    if crm and issue in responses.INVITATION_ISSUES
                    else None
                ),
            }
    return templates.TemplateResponse(
        request=request,
        name="exception_analysis.html",
        context={
            **view,
            **hub_context(request, record),
            "record_nav": exception_record_navigation(request, session, record),
            "review": review,
            "resolved": resolved,
            "can_decide": can_decide,
            "scope": scope,
            "origins": rca.origin_options(scope),
            "roles": rca.ROLES,
            "findings": rca.applicable_findings(findings.get(record.id, {}), scope),
            "finding_labels": FINDINGS,
            "batch_finding_links": batch_finding_links,
            "test_review": test_review,
            "capa_labels": CAPA,
            "comparison_labels": COMPARISON,
            "state": rca.fingerprint([(record, review)], findings, scope),
            "batch_available": any(
                item.id != identifier
                for group in batch_groups.values()
                for item, _ in group
            ),
            "pending": has_pending_review(review),
            "response_requests": responses.case_requests(session, record)
            if can_decide
            else {},
            "response_today": responses.today(),
            "response_contacts": response_contacts,
            "title": "Root cause analysis",
            "active": "exceptions",
        },
    )


def has_pending_review(review):
    return bool(
        review
        and (review.status == "to_do" or review.next_action.strip() or review.due_date)
    )


def rca_staff(request):
    actor = getattr(request.state, "portal_user", None)
    return (
        actor
        if actor
        and (getattr(actor, "is_nmvo", False) or getattr(actor, "is_admin", False))
        else None
    )


def rca_actor(request):
    actor = rca_staff(request)
    if actor is None:
        raise HTTPException(403, "An NMVO account is required.")
    return actor


def audit_actor(actor):
    if actor is None:
        return None
    email = getattr(actor, "email", "")
    return email if email and len(email) <= 100 else f"Portal user #{actor.id}"


def rca_decision(data, scope):
    if scope == "unconfirmed":
        raise HTTPException(
            409, "Confirm the initiating market and location before closing."
        )
    origin = data.get("origin")
    note = data.get("note", "").strip()
    if origin not in rca.origin_options(scope) or len(note) > 4000:
        raise HTTPException(
            422, "Choose an origin and use at most 4,000 characters for the note."
        )
    return origin, note


def save_rca_decisions(session, rows, findings, scope, origin, note, actor, anchor):
    try:
        for record, review in rows:
            decision = {
                "basis": rca.CLOSED_BASIS
                if scope != "foreign"
                else "foreign_support_complete",
                "origin": origin,
                "actor_id": actor.id,
                "responsibility": scope,
                "requesting_market": record.source_market,
                "reason": note,
                "resolved_at": datetime.now(UTC).isoformat(),
                "participant_finding_ids": {
                    role: event.id
                    for role, event in rca.applicable_findings(
                        findings.get(record.id, {}), scope
                    ).items()
                },
            }
            work.save(
                session,
                record,
                review.version if review else 0,
                record.payload_hash,
                {
                    "status": "resolved",
                    "cause": review.cause if review else "",
                    "findings": review.findings if review else "",
                    "analysis": review.analysis if review else None,
                    "next_action": "",
                    "due_date": None,
                    "review_reason": note,
                    "resolution": decision,
                },
                anchor,
                actor=audit_actor(actor),
            )
        session.commit()
    except (ValueError, IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(
            409, "The selected cases changed. Review them again."
        ) from None


@router.post("/exceptions/{identifier}/analysis/close", include_in_schema=False)
async def close_rca(request: Request, identifier: int, session: DbSession):
    actor = rca_actor(request)
    data = await review_form(request)
    record = session.get(
        NMVSException, identifier, with_for_update=True, populate_existing=True
    )
    if not record or record.source_namespace != queries.namespace(session):
        raise HTTPException(404, "Exception not found.")
    scope = rca.responsibility(session, record)
    origin, note = rca_decision(data, scope)
    review = session.get(
        ExceptionReview, identifier, with_for_update=True, populate_existing=True
    )
    rows = [(record, review)]
    findings = rca.participant_findings(session, [identifier], lock=True)
    if rca.resolved_for_source(review, record) or data.get("state") != rca.fingerprint(
        rows, findings, scope
    ):
        raise HTTPException(
            409, "The case changed. Review the latest findings before closing."
        )
    if has_pending_review(review) and data.get("complete_pending") != "yes":
        raise HTTPException(422, "Confirm that the pending follow-up can be closed.")
    save_rca_decisions(session, rows, findings, scope, origin, note, actor, identifier)
    return RedirectResponse(
        f"/exceptions/{identifier}/analysis?notice=case_closed", status_code=303
    )


@router.post("/exceptions/{identifier}/analysis/batches", include_in_schema=False)
async def close_rca_batches(request: Request, identifier: int, session: DbSession):
    actor = rca_actor(request)
    data = await review_form(request)
    record = current(session, identifier)
    confirming = data.get("command") == "close_batches"
    rows = rca.batch_rows(session, record, lock=confirming)
    anchor = next((row for row in rows if row[0].id == identifier), None)
    if not anchor:
        raise HTTPException(409, "The originating case changed. Review it again.")
    scope = rca.responsibility(session, record)
    origin, note = rca_decision(data, scope)
    groups = list(rca.batch_groups(rows).items())
    if not groups:
        raise HTTPException(409, "No matching open batch cases are available.")
    eligible = [row for _, group in groups for row in group]
    basis = [anchor, *(row for row in eligible if row[0].id != identifier)]
    findings = rca.participant_findings(
        session, [item.id for item, _ in basis], lock=confirming
    )
    test_workspace = getattr(request.app.state, "alert_desk_test_workspace", False)
    review_reasons = {}
    case_ids = {}
    if test_workspace:
        from app.alert_desk.test_workspace import (
            case_id_for_alert,
            individual_review_reasons,
        )

        _, review_reasons = individual_review_reasons(session, findings)
        review_reasons = {
            item.id: review_reasons[item.id]
            for item, _ in eligible
            if item.id in review_reasons
        }
        case_ids = {item.id: case_id_for_alert(item) for item, _ in eligible}
    state = rca.fingerprint(basis, findings, scope)
    if test_workspace:
        state = sha256(repr((state, sorted(review_reasons.items()))).encode()).hexdigest()
    if not confirming:
        if data.get("state") != rca.fingerprint([anchor], findings, scope):
            raise HTTPException(409, "The originating case changed. Review it again.")
        return templates.TemplateResponse(
            request=request,
            name="exception_rca_batches.html",
            context={
                "title": "Review batch closure",
                "active": "exceptions",
                "record": record,
                "groups": groups,
                "participant_findings": findings if test_workspace else None,
                "review_reasons": review_reasons,
                "case_ids": case_ids,
                "participant_roles": tuple((role, rca.ROLES[role]) for role in responses.applicable_roles(record)),
                "finding_labels": FINDINGS,
                "state": state,
                "origin": origin,
                "origin_label": rca.ORIGINS[origin],
                "note": note,
                "scope": scope,
            },
        )
    selected = {
        key
        for key, value in data.items()
        if key.startswith("batch_") and value == "yes"
    }
    if not selected or not selected <= {f"batch_{i}" for i in range(len(groups))}:
        raise HTTPException(422, "Select at least one batch from the preview.")
    if state != data.get("state"):
        raise HTTPException(409, "The batch selection changed. Review it again.")
    targets = [
        row
        for i, (_, group) in enumerate(groups)
        if f"batch_{i}" in selected
        for row in group
        if row[0].id not in review_reasons
    ]
    if not targets or any(
        f"batch_{i}" in selected and all(item.id in review_reasons for item, _ in group)
        for i, (_, group) in enumerate(groups)
    ):
        raise HTTPException(422, "Select batches with cases eligible for batch closure.")
    save_rca_decisions(
        session, targets, findings, scope, origin, note, actor, identifier
    )
    return RedirectResponse(
        f"/exceptions/{identifier}/analysis?notice=cases_closed", status_code=303
    )


@router.get("/exceptions/{identifier}/analysis/worksheet", include_in_schema=False)
def exception_analysis_worksheet(identifier: int, session: DbSession):
    current(session, identifier)
    return RedirectResponse(f"/exceptions/{identifier}/analysis", status_code=303)


@router.get("/exceptions/{identifier}/work-audit", include_in_schema=False)
def exception_work_audit(
    request: Request,
    identifier: int,
    session: DbSession,
    page: int = Query(1, ge=1, le=10000),
):
    record = current(session, identifier)
    rows, pagination = paged(
        session,
        select(ExceptionReviewEvent)
        .where(ExceptionReviewEvent.exception_id == identifier)
        .order_by(ExceptionReviewEvent.id.desc()),
        page,
    )
    return templates.TemplateResponse(
        request=request,
        name="exception_work_audit.html",
        context={
            "record_nav": exception_record_navigation(request, session, record),
            **queries.context(session),
            "record": record,
            "events": [event for (event,) in rows],
            "origin_labels": rca.ORIGINS,
            "pagination": pagination,
            "audit_fields": (
                "cause",
                "findings",
                "next_action",
                "due_date",
                "review_reason",
                "analysis",
                "resolution",
                "basis_payload_hash",
            ),
            "title": "Audit trail",
            "active": "exceptions",
        },
    )


@router.get("/exceptions/{identifier}/source", include_in_schema=False)
def exception_source(request: Request, identifier: int, session: DbSession):
    record = current(session, identifier)
    return templates.TemplateResponse(
        request=request,
        name="exception_source.html",
        context={
            "record_nav": exception_record_navigation(request, session, record),
            **queries.context(session),
            **queries.detail(session, record),
            "title": "Exception · Original data",
            "active": "exceptions",
        },
    )


async def review_form(request, *, expected_origin=None, max_fields=65):
    url = urlsplit(str(request.url))
    if request.headers.get("origin") != (
        expected_origin or f"{url.scheme}://{url.netloc}"
    ):
        message = (
            "Open the portal at its configured address and try again."
            if expected_origin
            else "Use the local exception review form."
        )
        raise HTTPException(403, message)
    if (
        request.headers.get("content-type", "").split(";", 1)[0]
        != "application/x-www-form-urlencoded"
    ):
        raise HTTPException(415, "Use the review form.")
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > 48000:
            raise HTTPException(413, "Review form is too large.")
    try:
        data = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=max_fields)
        if any(len(v) != 1 for v in data.values()):
            raise ValueError()
        return {k: v[0] for k, v in data.items()}
    except (ValueError, UnicodeError):
        raise HTTPException(422, "Invalid review form.") from None


def token(value):
    try:
        version, payload = value.split(":")
        if len(payload) != 64 or int(version) < 0:
            raise ValueError()
        return int(version), payload
    except (ValueError, AttributeError):
        raise HTTPException(422, "Invalid review version.") from None


@router.post("/exceptions/{identifier}/review", include_in_schema=False)
async def save_review(request: Request, identifier: int, session: DbSession):
    data = await review_form(request)
    record = session.scalar(
        select(NMVSException)
        .where(NMVSException.id == identifier)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    current(session, identifier)
    existing = session.get(ExceptionReview, identifier)
    command = data.get("command")
    if command not in ("save", "resolve", "reopen"):
        raise HTTPException(
            422, "Choose Save analysis, Resolve exception or Reopen exception."
        )
    if command == "reopen":
        if not existing or existing.status != "resolved":
            raise HTTPException(409, "Only resolved exceptions can be reopened.")
        reason = data.get("reopen_reason", "").strip()
        if not reason or len(reason) > 4000:
            raise HTTPException(
                422, "Give a reopening reason (up to 4,000 characters)."
            )
        values = work.reopen_values(existing, record, reason)
        try:
            work.save(
                session,
                record,
                *token(data.get("version")),
                values,
                identifier,
                actor=audit_actor(getattr(request.state, "portal_user", None)),
            )
            session.commit()
        except (ValueError, IntegrityError, StaleDataError):
            session.rollback()
            raise HTTPException(
                409, "This exception changed. Reload before reopening."
            ) from None
        return RedirectResponse(
            f"/exceptions/{identifier}/analysis?notice=reopened", status_code=303
        )
    if existing and existing.status == "resolved":
        raise HTTPException(
            409, "Reopen this exception before changing its analysis or resolution."
        )
    status = "resolved" if command == "resolve" else data.get("status")
    if status not in ("open", "to_do", "resolved"):
        raise HTTPException(
            422, "Choose Open or To do; use Resolve exception to finish."
        )
    if command == "save" and status == "resolved":
        raise HTTPException(422, "Use the explicit Resolve exception action.")
    values = {
        k: data.get(k, "").strip()
        for k in ("cause", "findings", "next_action", "review_reason")
    }
    if any(len(v) > 4000 for v in values.values()):
        raise HTTPException(422, "Use at most 4,000 characters per field.")
    if status == "resolved" and not values["review_reason"]:
        raise HTTPException(
            422, "Give a resolution reason before resolving this exception."
        )
    if status == "to_do" and not values["next_action"]:
        raise HTTPException(422, "Describe the next action for your to-do list.")
    try:
        due = date.fromisoformat(data["due_date"]) if data.get("due_date") else None
    except ValueError:
        raise HTTPException(422, "Use a valid follow-up date.") from None
    try:
        analysis = causes.parse(data, existing.analysis if existing else None)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    resolution = None
    if command == "resolve":
        basis = data.get("resolution_basis")
        if basis not in ("confirmed_cause", "no_further_action"):
            raise HTTPException(422, "Choose a resolution basis.")
        if basis == "confirmed_cause" and (
            not analysis
            or analysis.get("confidence") != "confirmed"
            or analysis.get("category") == "unknown"
        ):
            raise HTTPException(
                422,
                "Confirm the cause with supporting evidence, or document why no further local action is required.",
            )
        if (
            existing
            and (
                existing.status == "to_do"
                or existing.next_action.strip()
                or existing.due_date
            )
            or values["next_action"]
            or due
        ) and data.get("complete_pending") != "yes":
            raise HTTPException(
                422,
                "Confirm that pending follow-up is completed or superseded, and explain this in the resolution reason.",
            )
        resolution = {
            "basis": basis,
            "resolved_at": datetime.now(UTC).isoformat(),
            "reason": values["review_reason"],
            "pending_follow_up_acknowledged": data.get("complete_pending") == "yes",
        }
    try:
        work.save(
            session,
            record,
            *token(data.get("version")),
            {
                **values,
                "status": status,
                "due_date": due,
                "analysis": analysis,
                "resolution": resolution,
            },
            identifier,
        )
        session.commit()
    except (ValueError, IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(
            409, "This exception or review changed. Reload before saving."
        ) from None
    return RedirectResponse(
        f"/exceptions/{identifier}/analysis?notice={'resolved' if command == 'resolve' else 'saved'}",
        status_code=303,
    )


@router.get("/exceptions/{identifier}/similar", include_in_schema=False)
def similar_reviews(request: Request, identifier: int, session: DbSession):
    record = current(session, identifier)
    return templates.TemplateResponse(
        request=request,
        name="exception_similar.html",
        context={
            **queries.context(session),
            "record": record,
            "review": session.get(ExceptionReview, identifier),
            "candidates": work.similar(session, record),
            "can_transfer": causes.transferable(
                session.get(ExceptionReview, identifier)
            )
            and session.get(ExceptionReview, identifier).status == "resolved",
            "active": "exceptions",
            "title": "Review similar exceptions",
        },
    )


@router.post("/exceptions/{identifier}/similar", include_in_schema=False)
async def apply_similar(request: Request, identifier: int, session: DbSession):
    data = await review_form(request)
    if data.get("command") != "resolve_similar":
        raise HTTPException(422, "Use the explicit Resolve selected exceptions action.")
    current(session, identifier)
    # Serialise source review and candidate edits, always in ID order.
    try:
        ids = sorted(
            {identifier} | {int(k[7:]) for k in data if k.startswith("target_")}
        )
    except ValueError:
        raise HTTPException(422, "Invalid exception selection.") from None
    if len(ids) <= 1 or len(ids) > 51:
        raise HTTPException(422, "Select between 1 and 50 similar exceptions.")
    records = {
        v.id: v
        for v in session.scalars(
            select(NMVSException)
            .where(NMVSException.id.in_(ids))
            .order_by(NMVSException.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    session.scalars(
        select(ExceptionReview)
        .where(ExceptionReview.exception_id.in_(ids))
        .order_by(ExceptionReview.exception_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    record = records[identifier]
    review = session.get(ExceptionReview, identifier)
    if not causes.transferable(review) or review.status != "resolved":
        raise HTTPException(
            422,
            "Resolve the original exception with a confirmed, classified root cause and evidence first.",
        )
    if (
        token(data.get("version")) != (review.version, record.payload_hash)
        or review.basis_payload_hash != record.payload_hash
    ):
        raise HTTPException(
            409, "The original assessment changed. Reload and check the selection."
        )
    allowed = {v.id for v, _ in work.similar(session, record)}
    if any(i not in allowed for i in ids if i != identifier):
        raise HTTPException(
            409,
            "The selection changed or contains an unrelated exception. Reload the preview.",
        )
    reason = data.get("reason", "").strip()
    if not reason or len(reason) > 4000:
        raise HTTPException(
            422,
            "Explain why the root cause applies to this selection (up to 4,000 characters).",
        )
    try:
        for i in ids:
            if i == identifier:
                continue
            existing = session.get(ExceptionReview, i)
            if existing and (
                existing.status == "to_do"
                or existing.next_action.strip()
                or existing.due_date
            ):
                raise ValueError(
                    "A selected exception has a pending to-do. Review it individually first."
                )
            # Preserve each target's own findings and follow-up rather than overwrite them.
            values = {
                k: getattr(existing, k) if existing else None if k == "due_date" else ""
                for k in work.FIELDS
            }
            values.update(
                status="resolved",
                cause=review.cause,
                review_reason=reason,
                resolution={
                    "basis": "shared_cause",
                    "reason": reason,
                    "resolved_at": datetime.now(UTC).isoformat(),
                    "originating_exception_id": identifier,
                    "originating_review_version": review.version,
                    "originating_payload_hash": record.payload_hash,
                },
                analysis={
                    "catalogue_version": 1,
                    "category": review.analysis["category"],
                    "confidence": "suspected",
                    "checks": {},
                    "shared_from": identifier,
                },
            )
            work.save(
                session, records[i], *token(data.get(f"target_{i}")), values, identifier
            )
        session.commit()
    except (ValueError, IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(
            409,
            "The selection changed or has pending work. Reload and review individually.",
        ) from None
    return RedirectResponse(
        f"/exceptions/{identifier}/analysis?notice=similar_resolved", status_code=303
    )


def repeat_resolution_values(review, sequence, reason):
    values = (
        {field: getattr(review, field) for field in work.FIELDS}
        if review
        else {
            "cause": "",
            "findings": "",
            "next_action": "",
            "due_date": None,
            "analysis": None,
        }
    )
    values.update(
        status="resolved",
        review_reason=reason,
        resolution={
            "basis": "observed_repeat_export"
            if sequence["repeat"]["operation"] == "Export"
            else "observed_repeat_destroy",
            "reason": reason,
            "resolved_at": datetime.now(UTC).isoformat(),
            "pack_audit_report_id": sequence["report_id"],
            "earlier_transaction_id": sequence["previous"]["transaction_id"],
            "repeat_transaction_id": sequence["repeat"]["transaction_id"],
        },
    )
    return values


@router.post("/exceptions/{identifier}/resolve-export", include_in_schema=False)
@router.post("/exceptions/{identifier}/resolve-repeat", include_in_schema=False)
async def resolve_repeat(request: Request, identifier: int, session: DbSession):
    data = await review_form(request)
    record = current(session, identifier)
    session.refresh(record, with_for_update=True)
    review = session.get(ExceptionReview, identifier, with_for_update=True)
    if review and (
        review.status in ("resolved", "to_do")
        or review.next_action.strip()
        or review.due_date
    ):
        raise HTTPException(
            409, "Review the existing resolution or pending follow-up individually."
        )
    sequence = repeat_evidence.repeat_sequence(session, record)
    if not sequence or data.get("report_id") != str(sequence["report_id"]):
        raise HTTPException(409, "Reload and check the current pack audit evidence.")
    reason = data.get("reason", "").strip()
    if not reason or len(reason) > 4000:
        raise HTTPException(
            422, "Give a local resolution reason (up to 4,000 characters)."
        )
    values = repeat_resolution_values(review, sequence, reason)
    try:
        work.save(session, record, *token(data.get("version")), values, identifier)
        session.commit()
    except (ValueError, IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(
            409, "This exception changed. Reload before resolving."
        ) from None
    return RedirectResponse(
        f"/exceptions/{identifier}/analysis?notice=resolved", status_code=303
    )


def export_batch_candidates(session, record, *, lock=False):
    if repeat_evidence.operation_for(record) != repeat_evidence.OPERATIONS["EXPORTED"]:
        raise HTTPException(422, "Batch resolution is available for Export exceptions.")
    identity = repeat_evidence.batch_identity(record)
    if not identity:
        raise HTTPException(422, "An exact product and batch are required.")
    namespace, scheme, code, batch = identity
    query = (
        select(NMVSException)
        .where(
            NMVSException.source_namespace == namespace,
            NMVSException.product_code_scheme == scheme,
            NMVSException.product_code == code,
            or_(
                NMVSException.stored_batch == batch,
                NMVSException.provided_batch == batch,
            ),
            NMVSException.source_market == record.source_market,
            NMVSException.source_location_id == record.source_location_id,
            NMVSException.error_code == "A7",
        )
        .order_by(NMVSException.id)
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    records = session.scalars(query).all()
    if lock:
        anchor = next((item for item in records if item.id == record.id), None)
        if not anchor or repeat_evidence.batch_identity(anchor) != identity:
            raise HTTPException(409, "The batch changed. Reload the preview.")
    records = [
        item
        for item in records
        if repeat_evidence.batch_identity(item) == identity
        and repeat_evidence.operation_for(item)
        == repeat_evidence.OPERATIONS["EXPORTED"]
        and item.source_market == record.source_market
        and item.source_location_id == record.source_location_id
        and item.business_process == record.business_process
        and item.is_intermarket == record.is_intermarket
    ]
    query = (
        select(ExceptionReview)
        .where(ExceptionReview.exception_id.in_([item.id for item in records]))
        .order_by(ExceptionReview.exception_id)
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    reviews = {review.exception_id: review for review in session.scalars(query)}
    return [(item, reviews.get(item.id)) for item in records]


def export_batch_selection(rows, sequence, record):
    eligible = [
        (item, review)
        for item, review in rows
        if not review
        or not (
            review.status in ("resolved", "to_do")
            or review.next_action.strip()
            or review.due_date
        )
    ]
    state = "|".join(
        f"{item.id}:{item.payload_hash}:{review.version if review else 0}"
        for item, review in eligible
    )
    fingerprint = sha256(
        f"{sequence['report_id']}|{record.payload_hash}|{state}".encode()
    ).hexdigest()
    return eligible, fingerprint


@router.get("/exceptions/{identifier}/resolve-export-batch", include_in_schema=False)
def export_batch_preview(request: Request, identifier: int, session: DbSession):
    record = current(session, identifier)
    sequence = repeat_evidence.repeat_sequence(session, record)
    if not sequence:
        raise HTTPException(409, "A matching pack audit sequence is required.")
    rows = export_batch_candidates(session, record)
    eligible, fingerprint = export_batch_selection(rows, sequence, record)
    return templates.TemplateResponse(
        request=request,
        name="exception_resolve_export_batch.html",
        context={
            **queries.context(session),
            "record": record,
            "batch": repeat_evidence.batch_identity(record)[-1],
            "eligible": eligible,
            "skipped": len(rows) - len(eligible),
            "fingerprint": fingerprint,
            "title": "Resolve matching batch exceptions",
            "active": "exceptions",
        },
    )


@router.post("/exceptions/{identifier}/resolve-export-batch", include_in_schema=False)
async def resolve_export_batch(request: Request, identifier: int, session: DbSession):
    data = await review_form(request)
    record = current(session, identifier)
    rows = export_batch_candidates(session, record, lock=True)
    sequence = repeat_evidence.repeat_sequence(session, record)
    if not sequence:
        raise HTTPException(409, "The pack audit evidence changed. Reload the preview.")
    eligible, fingerprint = export_batch_selection(rows, sequence, record)
    if not eligible or data.get("fingerprint") != fingerprint:
        raise HTTPException(
            409, "The selection changed. Reload the preview before resolving."
        )
    reason = data.get("reason", "").strip()
    if not reason or len(reason) > 4000:
        raise HTTPException(
            422, "Give a local resolution reason (up to 4,000 characters)."
        )
    try:
        for item, review in eligible:
            values = repeat_resolution_values(review, sequence, reason)
            values["resolution"].update(
                basis="batch_export_pattern",
                evidence_exception_id=identifier,
                evidence_payload_hash=record.payload_hash,
                pack_audit_scope="originating_pack_only",
            )
            work.save(
                session,
                item,
                review.version if review else 0,
                item.payload_hash,
                values,
                identifier,
            )
        session.commit()
    except (ValueError, IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(
            409, "The selection changed. No exceptions were resolved."
        ) from None
    return RedirectResponse(
        f"/exceptions/{identifier}/analysis?notice=batch_resolved", status_code=303
    )


@router.get("/exceptions/{identifier}/reopen-batch", include_in_schema=False)
def batch_reopen_view(
    request: Request, identifier: int, session: DbSession, after: int = Query(0, ge=0)
):
    record = current(session, identifier)
    identity = repeat_evidence.batch_identity(record)
    if not identity:
        raise HTTPException(422, "An exact product and batch are required.")
    namespace, scheme, code, batch = identity
    rows = session.execute(
        select(NMVSException, ExceptionReview)
        .join(ExceptionReview, ExceptionReview.exception_id == NMVSException.id)
        .where(
            NMVSException.id > after,
            NMVSException.source_namespace == namespace,
            NMVSException.product_code_scheme == scheme,
            NMVSException.product_code == code,
            or_(
                NMVSException.stored_batch == batch,
                NMVSException.provided_batch == batch,
            ),
            ExceptionReview.status == "resolved",
        )
        .order_by(NMVSException.id)
    )
    candidates = []
    for candidate, review in rows:
        if repeat_evidence.batch_identity(candidate) == identity:
            candidates.append((candidate, review))
            if len(candidates) == 51:
                break
    return templates.TemplateResponse(
        request=request,
        name="exception_reopen_batch.html",
        context={
            **queries.context(session),
            "record": record,
            "batch": batch,
            "candidates": candidates[:50],
            "more": len(candidates) > 50,
            "title": "Reopen batch exceptions",
            "active": "exceptions",
        },
    )


@router.post("/exceptions/{identifier}/reopen-batch", include_in_schema=False)
async def reopen_batch(request: Request, identifier: int, session: DbSession):
    return await reopen_selection(request, session, identifier)


@router.post("/exceptions/reopen-selected", include_in_schema=False)
async def reopen_from_list(request: Request, session: DbSession):
    return await reopen_selection(request, session)


async def reopen_selection(request, session, identifier=None):
    data = await review_form(request)
    anchor = current(session, identifier) if identifier is not None else None
    reason = data.get("reason", "").strip()
    try:
        ids = {int(field[7:]) for field in data if field.startswith("target_")}
    except ValueError:
        raise HTTPException(422, "Invalid exception selection.") from None
    if not 1 <= len(ids) <= 50 or not reason or len(reason) > 4000:
        raise HTTPException(
            422, "Select 1 to 50 exceptions and give a reopening reason."
        )
    records = {
        row.id: row
        for row in session.scalars(
            select(NMVSException)
            .where(NMVSException.id.in_(ids | ({identifier} if anchor else set())))
            .order_by(NMVSException.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    namespace = queries.namespace(session)
    identity = repeat_evidence.batch_identity(records[anchor.id]) if anchor else None
    if any(
        key not in records
        or records[key].source_namespace != namespace
        or (
            anchor
            and (
                not identity or repeat_evidence.batch_identity(records[key]) != identity
            )
        )
        for key in ids
    ):
        raise HTTPException(
            409, "The selection changed or is outside the permitted scope."
        )
    reviews = {
        row.exception_id: row
        for row in session.scalars(
            select(ExceptionReview)
            .where(ExceptionReview.exception_id.in_(ids))
            .order_by(ExceptionReview.exception_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    if any(key not in reviews or reviews[key].status != "resolved" for key in ids):
        raise HTTPException(
            409, "The selection changed. Reload the list of resolved exceptions."
        )
    try:
        for key in sorted(ids):
            record = records[key]
            work.save(
                session,
                record,
                *token(data.get(f"target_{key}")),
                work.reopen_values(reviews[key], record, reason),
                identifier if anchor else key,
            )
        session.commit()
    except (ValueError, IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(
            409, "The selection changed. No exceptions were reopened."
        ) from None
    if not anchor:
        filters = dict(request.query_params)
        filters.update(work_status="open", page=1, reopened=len(ids))
        return RedirectResponse("/exceptions?" + urlencode(filters), status_code=303)
    return RedirectResponse(
        f"/exceptions/{identifier}/reopen-batch?reopened={len(ids)}", status_code=303
    )
