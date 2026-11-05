from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.core.config.settings import get_settings
from app.domain.exceptions import intelligence, repeat_evidence
from app.domain.exceptions import review as work
from app.domain.models import ExceptionReview, IntelligenceRuleRevision, NMVSException
from app.portal import exception_queries
from app.portal.exception_routes import repeat_resolution_values, review_form, token
from app.portal.routes import DbSession, templates

router = APIRouter()


def context(session):
    namespace = exception_queries.namespace(session)
    settings = get_settings()
    return {
        "scope": intelligence.current_scope(session, namespace),
        "operations": repeat_evidence.OPERATIONS,
        "rule_id": intelligence.RULE_ID,
        "evaluator_version": intelligence.EVALUATOR_VERSION,
        "title": "Intelligence rules",
        "active": "intelligence",
        "search_enabled": bool(
            settings.openai_api_key and settings.openai_search_model
        ),
    }


@router.get("/intelligence/rules", include_in_schema=False)
def rules(
    request: Request,
    session: DbSession,
    start: date | None = None,
    end: date | None = None,
    operation: str = Query("", max_length=20),
    market: str = Query("", max_length=10),
    preview: bool = False,
    matched_only: bool = False,
):
    validate_scope(operation, market)
    today = datetime.now(UTC).date()
    end = end or today
    start = start or end - timedelta(days=29)
    if end < start or (end - start).days > 366 or end == date.max:
        raise HTTPException(422, "Select a period of at most 367 days.")
    ctx = context(session)
    results = []
    limited = False
    if preview:
        source_operation = NMVSException.evidence["attemptedOperation"].as_string()
        statement = (
            select(NMVSException, ExceptionReview)
            .outerjoin(
                ExceptionReview, ExceptionReview.exception_id == NMVSException.id
            )
            .where(
                NMVSException.source_namespace == exception_queries.namespace(session),
                NMVSException.error_code == "A7",
                NMVSException.alert_at >= datetime.combine(start, datetime.min.time()),
                NMVSException.alert_at
                < datetime.combine(end + timedelta(days=1), datetime.min.time()),
                source_operation.in_(
                    [operation] if operation else list(repeat_evidence.OPERATIONS)
                ),
            )
        )
        if market:
            statement = statement.where(NMVSException.source_market == market)
        rows = session.execute(
            statement.order_by(
                NMVSException.alert_at.desc(), NMVSException.id.desc()
            ).limit(101)
        ).all()
        limited = len(rows) > 100
        results = evaluate_rows(session, rows[:100], ctx["scope"])
        if matched_only:
            results = [row for row in results if row["sequence"]]
    return templates.TemplateResponse(
        request=request,
        name="intelligence_rules.html",
        context={
            **ctx,
            "start": start,
            "end": end,
            "operation": operation,
            "market": market,
            "preview": preview,
            "matched_only": matched_only,
            "results": results,
            "limited": limited,
        },
    )


def validate_scope(operation, market):
    if operation and operation not in repeat_evidence.OPERATIONS:
        raise HTTPException(422, "Select a supported operation.")
    if market and (
        not market.isascii()
        or not market.isalpha()
        or not market.isupper()
        or len(market) not in (2, 3)
    ):
        raise HTTPException(422, "Use a two or three letter market code.")


@router.post("/intelligence/rules", include_in_schema=False)
async def save_rule_scope(request: Request, session: DbSession):
    data = await review_form(request)
    namespace = exception_queries.namespace(session)
    if not namespace:
        raise HTTPException(409, "Import exceptions before configuring this rule.")
    operation = data.get("operation", "")
    market = data.get("market", "").strip().upper()
    validate_scope(operation, market)
    scope = intelligence.current_scope(session, namespace)
    if data.get("version") != str(scope.version):
        raise HTTPException(409, "The rule changed. Reload the configuration.")
    if (operation, market) != (scope.operation, scope.market):
        session.add(
            IntelligenceRuleRevision(
                source_namespace=namespace,
                version=scope.version + 1,
                operation=operation,
                market=market,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                409, "The rule changed. Reload the configuration."
            ) from None
    return RedirectResponse("/intelligence/rules", status_code=303)


def evaluate_rows(session, rows, scope):
    results = []
    for record, review in rows:
        sequence, explanation = intelligence.evaluate(session, record, scope)
        eligible = bool(sequence and intelligence.can_resolve(review))
        if sequence and not eligible:
            explanation += " Already resolved or pending individual follow-up."
        results.append(
            {
                "record": record,
                "sequence": sequence,
                "explanation": explanation,
                "eligible": eligible,
            }
        )
    return results


def selected_rows(session, data, *, lock=False):
    try:
        targets = {
            int(field[7:]): token(value)
            for field, value in data.items()
            if field.startswith("target_")
        }
    except ValueError:
        raise HTTPException(422, "Invalid exception selection.") from None
    if not 1 <= len(targets) <= 40:
        raise HTTPException(422, "Select between 1 and 40 exceptions.")
    namespace = exception_queries.namespace(session)
    statement = (
        select(NMVSException)
        .where(
            NMVSException.id.in_(targets), NMVSException.source_namespace == namespace
        )
        .order_by(NMVSException.id)
    )
    reviews = (
        select(ExceptionReview)
        .where(ExceptionReview.exception_id.in_(targets))
        .order_by(ExceptionReview.exception_id)
    )
    if lock:
        statement = statement.with_for_update().execution_options(
            populate_existing=True
        )
        reviews = reviews.with_for_update().execution_options(populate_existing=True)
    records = session.scalars(statement).all()
    current = {review.exception_id: review for review in session.scalars(reviews)}
    if len(records) != len(targets) or any(
        targets[record.id]
        != (
            current[record.id].version if record.id in current else 0,
            record.payload_hash,
        )
        for record in records
    ):
        raise HTTPException(
            409, "The selection changed. Return to Exceptions and select it again."
        )
    return [(record, current.get(record.id)) for record in records], targets


def fingerprint(results, scope, targets):
    parts = [
        intelligence.RULE_ID,
        str(intelligence.EVALUATOR_VERSION),
        str(scope.version),
    ]
    parts.extend(
        f"{row['record'].id}:{row['sequence']['report_id']}:{row['eligible']}"
        if row["sequence"]
        else f"{row['record'].id}:{row['explanation']}"
        for row in results
    )
    parts.extend(
        f"{key}:{version}:{digest}"
        for key, (version, digest) in sorted(targets.items())
    )
    return sha256("|".join(parts).encode()).hexdigest()


@router.post("/intelligence/apply", include_in_schema=False)
async def apply(request: Request, session: DbSession):
    data = await review_form(request)
    confirm = data.get("confirm") == "yes"
    rows, targets = selected_rows(session, data, lock=confirm)
    ctx = context(session)
    scope = ctx["scope"]
    results = evaluate_rows(session, rows, scope)
    digest = fingerprint(results, scope, targets)
    eligible = [row for row in results if row["eligible"]]
    if not confirm:
        return templates.TemplateResponse(
            request=request,
            name="intelligence_apply.html",
            context={
                **ctx,
                "results": results,
                "targets": targets,
                "fingerprint": digest,
                "eligible": eligible,
            },
        )
    if not eligible or data.get("fingerprint") != digest:
        raise HTTPException(409, "Rule results changed. Preview the selection again.")
    reason = data.get("reason", "").strip()
    if not reason or len(reason) > 4000:
        raise HTTPException(
            422, "Give a local resolution reason (up to 4,000 characters)."
        )
    reviews = {record.id: review for record, review in rows}
    try:
        for row in eligible:
            record = row["record"]
            values = repeat_resolution_values(
                reviews[record.id], row["sequence"], reason
            )
            values["resolution"].update(
                rule_id=intelligence.RULE_ID,
                rule_version=scope.version,
                evaluator_version=intelligence.EVALUATOR_VERSION,
                rule_scope={"operation": scope.operation, "market": scope.market},
            )
            work.save(session, record, *targets[record.id], values, record.id)
        session.commit()
    except (IntegrityError, StaleDataError, ValueError):
        session.rollback()
        raise HTTPException(
            409, "The selection changed. No exceptions were resolved."
        ) from None
    return RedirectResponse(
        "/exceptions?"
        + urlencode({"work_status": "resolved", "rule_applied": len(eligible)}),
        status_code=303,
    )


@router.post("/intelligence/interpret", include_in_schema=False)
async def interpret_search(request: Request, session: DbSession):
    import httpx
    from starlette.concurrency import run_in_threadpool

    from app.domain.exceptions.search_language import interpret

    data = await review_form(request)
    settings = get_settings()
    if not settings.openai_api_key or not settings.openai_search_model:
        raise HTTPException(503, "Configure OpenAI search before using language input.")
    question = data.get("question", "").strip()
    if not question or len(question) > 500:
        raise HTTPException(422, "Enter a search question of up to 500 characters.")
    try:
        draft = await run_in_threadpool(interpret, question, settings)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(
            502,
            "The search question could not be interpreted. Use the filters to continue.",
        ) from None
    today = datetime.now(UTC).date()
    return templates.TemplateResponse(
        request=request,
        name="intelligence_search_draft.html",
        context={
            **context(session),
            "draft": draft,
            "question": question,
            "end": today,
            "start": today - timedelta(days=draft.days - 1) if draft else None,
        },
    )
