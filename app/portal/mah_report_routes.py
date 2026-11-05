"""Read-only internal drafts for A2 and A3 by provisional SAI holder."""

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from app.domain.models import ExceptionPublication, NMVSException
from app.domain.uploads.service import covered
from app.portal import exception_queries
from app.portal.routes import DbSession, templates

router = APIRouter()


def month_bounds(month, today):
    current = today.replace(day=1)
    if not month:
        month = (current - timedelta(days=1)).strftime("%Y-%m")
    try:
        first = date.fromisoformat(month + "-01")
    except ValueError:
        raise HTTPException(
            422, "Select a completed month in YYYY-MM format."
        ) from None
    if first >= current or first.strftime("%Y-%m") != month:
        raise HTTPException(422, "Select a completed month in YYYY-MM format.")
    end = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (
        month,
        datetime.combine(first, datetime.min.time()),
        datetime.combine(end, datetime.min.time()),
    )


def group_alerts(rows):
    groups = defaultdict(list)
    for row in rows:
        record = row["record"]
        product = (
            ("GTIN", record.gtin14)
            if record.gtin14
            else (record.product_code_scheme, record.product_code)
        )
        batch = record.provided_batch or record.stored_batch
        groups[(record.error_code, product, batch)].append(row)
    result = []
    for (error, product, batch), members in groups.items():
        records = [member["record"] for member in members]
        result.append(
            {
                "error": error,
                "product": product[1],
                "name": members[0]["name"],
                "batch": batch,
                "members": members,
                "locations": len(
                    {
                        (record.source_market, record.source_location_id)
                        for record in records
                        if record.source_market and record.source_location_id
                    }
                ),
                "unknown_locations": sum(
                    not (record.source_market and record.source_location_id)
                    for record in records
                ),
                "serials": len(
                    {record.serial_number for record in records if record.serial_number}
                ),
            }
        )
    return sorted(
        result,
        key=lambda row: (
            row["error"],
            -len(row["members"]),
            row["product"] or "",
            row["batch"] or "",
        ),
    )


@router.get("/reports/mah", include_in_schema=False)
def mah_monthly_report(
    request: Request,
    session: DbSession,
    month: str = Query("", max_length=7),
    holder: int | None = Query(None, ge=0),
):
    today = datetime.now(UTC).date()
    month, start, end = month_bounds(month, today)
    context = exception_queries.context(session)
    namespace = context["source_namespace"]
    records = session.scalars(
        select(NMVSException)
        .where(
            NMVSException.source_namespace == namespace,
            NMVSException.alert_at >= start,
            NMVSException.alert_at < end,
            NMVSException.error_code.in_(("A2", "A3")),
        )
        .order_by(NMVSException.alert_at, NMVSException.id)
    ).all()
    by_holder = defaultdict(list)
    for offset in range(0, len(records), 500):
        for row in exception_queries.enriched(session, records[offset : offset + 500]):
            by_holder[
                row["holder_id"] if row["holder_id"] and row["holder"] else 0
            ].append(row)

    if holder is not None and holder not in by_holder:
        raise HTTPException(404, "No draft for this MAH and month.")
    reports = sorted(
        [
            {
                "id": key,
                "name": rows[0]["holder"] if key else "Unassigned",
                "counts": Counter(row["record"].error_code for row in rows),
            }
            for key, rows in by_holder.items()
        ],
        key=lambda row: (row["id"] == 0, row["name"].casefold(), row["id"]),
    )

    windows = session.scalars(
        select(ExceptionPublication).where(
            ExceptionPublication.source_namespace == namespace,
            ExceptionPublication.period_start < end,
            ExceptionPublication.period_end >= start,
        )
    ).all()
    days = (end - start).days
    complete = sum(
        covered(
            windows,
            start + timedelta(days=i),
            start + timedelta(days=i + 1, milliseconds=-1),
        )
        for i in range(days)
    )
    return templates.TemplateResponse(
        request=request,
        name="mah_monthly_report.html",
        context={
            **context,
            "title": "MAH monthly reports",
            "active": "mah_reports",
            "month": month,
            "latest_month": (today.replace(day=1) - timedelta(days=1)).strftime(
                "%Y-%m"
            ),
            "reports": reports,
            "selected": next((row for row in reports if row["id"] == holder), None),
            "groups": group_alerts(by_holder[holder]) if holder is not None else [],
            "complete": complete,
            "days": days,
            "total": len(records),
        },
    )
