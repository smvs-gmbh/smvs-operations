"""Retained query periods, including successfully imported days without alerts."""

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app.domain.models import ExceptionPublication


def date_scope(session, namespace):
    first, last = session.execute(
        select(func.min(ExceptionPublication.period_start), func.max(ExceptionPublication.period_end))
        .where(ExceptionPublication.source_namespace == namespace)
    ).one()
    today = datetime.now(UTC).date()
    lower = first.date() if first else None
    upper = min(last.date(), today) if last else None
    if lower and lower > upper:
        lower = upper = None
    presets = []
    if lower:
        for months, label in ((1, "Last month"), (3, "Last 3 months"), (12, "Last year")):
            index = upper.year * 12 + upper.month - 1 - months
            year, month = divmod(index, 12)
            previous = date(year, month + 1, min(upper.day, monthrange(year, month + 1)[1]))
            presets.append((str(months), label, max(lower, previous + timedelta(days=1)), upper))
        presets.append(("all", "All", lower, upper))
    return {"date_min": lower, "date_max": upper, "date_presets": presets}


def resolve_period(request, start, end, scope, *, default_days=30):
    """Freeze shortcuts and old out-of-bounds links to explicit retained dates."""
    upper, lower = scope["date_max"], scope["date_min"]
    end = end or upper or datetime.now(UTC).date()
    start = start or end - timedelta(days=min(default_days - 1, (end - date.min).days))
    original = (start, end)
    preset = request.query_params.get("period")
    for key, _, first, last in scope["date_presets"]:
        if preset == key:
            start, end = first, last
            break
    # Leave reversed ranges to the route's validation; never silently swap them.
    if lower and start <= end:
        start = min(max(start, lower), upper)
        end = min(max(end, lower), upper)
    elif not lower and start <= end:
        # No selectable history: do not aggregate arbitrarily large URL ranges.
        start = end = datetime.now(UTC).date()
    if preset or (start, end) != original:
        params = [(k, v) for k, v in request.query_params.multi_items()
                  if k not in {"start", "end", "period", "page"}]
        params.extend((("start", start.isoformat()), ("end", end.isoformat())))
        return start, end, RedirectResponse(request.url.path + "?" + urlencode(params), status_code=303)
    return start, end, None
