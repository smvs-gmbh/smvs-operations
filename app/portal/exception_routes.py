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

from app.core.config import get_settings
from app.domain.exceptions import causes, repeat_evidence
from app.domain.exceptions import review as work
from app.domain.exceptions.list_search import interpret_filters
from app.domain.models import ExceptionReview, ExceptionReviewEvent, NMVSException
from app.portal import exception_queries as queries
from app.portal.queries import paged
from app.portal.record_navigation import list_record_navigation
from app.portal.routes import DbSession, templates

router = APIRouter()


@router.get("/exceptions", include_in_schema=False)
def exception_list(
    request: Request,
    session: DbSession,
    start: date | None = None,
    end: date | None = None,
    q: str = Query("", max_length=150),
    error: str = Query("", max_length=100),
    market: str = Query("", max_length=100),
    organisation: str = Query("", max_length=100),
    location: str = Query("", max_length=100),
    process: str = Query("", max_length=255),
    date_quality: str = Query("", pattern="^(|unresolved)$"),
    intermarket: str = Query("", pattern="^(|yes|no|unset)$"),
    work_status: str = Query("open", pattern="^(open|to_do|resolved|all)$"),
    page: int = Query(1, ge=1, le=10000),
):
    from app.portal.table_views import prepare
    prepare(request, session, "exceptions")
    end = end or datetime.now(UTC).date()
    start = start or end - timedelta(days=29)
    if end < start or (end - start).days > 366:
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
        market=market,
        organisation=organisation,
        location=location,
        process=process,
        date_quality=date_quality,
        intermarket=intermarket,
        page=page, view_request=request,
        work_status=work_status,
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
                        for key in (*EXCEPTION_NAV_FILTERS, *(k for k in request.query_params if k.startswith("tv_")))
                        if key in request.query_params
                    },
                }
            ),
            "start": start,
            "end": end,
            "q": q,
            "error": error,
            "market": market,
            "organisation_filter": organisation,
            "location_filter": location,
            "process": process,
            "date_quality": date_quality,
            "intermarket": intermarket,
            "work_status": work_status,
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
    "market",
    "organisation",
    "location",
    "process",
    "date_quality",
    "intermarket",
    "work_status",
)


def exception_record_navigation(request, session, record):
    params = request.query_params
    filters = {key: params[key] for key in EXCEPTION_NAV_FILTERS if key in params}
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
    statement, ordering = queries.listing_statement(
        session, start=start, end=end, **filters
    )
    view_params = {k: v for k, v in params.items() if k.startswith("tv_")}
    query = "?" + urlencode({"nav_start": start, "nav_end": end, **filters, **view_params})
    suffix = request.url.path.removeprefix(f"/exceptions/{record.id}")
    navigation = list_record_navigation(
        session,
        statement,
        NMVSException.id,
        record.id,
        ordering,
        "/exceptions",
        "Exceptions",
        view_request=request, table_key="exceptions",
        suffix=suffix,
        query=query,
        back_query="?" + urlencode({"start": start, "end": end, **filters, **view_params}),
    )
    navigation["query"] = query
    return navigation


@router.get("/exceptions/{identifier}", include_in_schema=False)
def exception_detail(request: Request, identifier: int, session: DbSession):
    record = current(session, identifier)
    return templates.TemplateResponse(
        request=request,
        name="exception_detail.html",
        context={
            **queries.context(session),
            **queries.detail(session, record),
            "review": session.get(ExceptionReview, identifier),
            "record_nav": exception_record_navigation(request, session, record),
            "title": record.unique_alert_id,
            "active": "exceptions",
        },
    )


@router.get("/exceptions/{identifier}/analysis", include_in_schema=False)
def exception_analysis(request: Request, identifier: int, session: DbSession):
    record = current(session, identifier)
    review = session.get(ExceptionReview, identifier)
    operation = repeat_evidence.operation_for(record)
    return templates.TemplateResponse(
        request=request,
        name="exception_analysis.html",
        context={
            "record_nav": exception_record_navigation(request, session, record),
            **queries.context(session),
            **queries.detail(session, record),
            "review": review,
            "categories": causes.CATEGORIES,
            "confidence_labels": causes.CONFIDENCE,
            "check_labels": causes.CHECKS,
            "repeat_sequence": repeat_evidence.repeat_sequence(session, record),
            "repeat_history": repeat_evidence.history(session, record)
            if operation
            else None,
            "repeat_operation": operation,
            "batch_identity": repeat_evidence.batch_identity(record),
            "pending_work": bool(
                review
                and (
                    review.status == "to_do"
                    or review.next_action.strip()
                    or review.due_date
                )
            ),
            "can_transfer": causes.transferable(review) and review.status == "resolved",
            "title": "Root cause analysis",
            "active": "exceptions",
        },
    )


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


async def review_form(request, *, expected_origin=None):
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
        data = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=65)
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
            work.save(session, record, *token(data.get("version")), values, identifier)
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
