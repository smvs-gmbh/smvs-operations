"""Monthly counts of retained NMVS alerts and their drill-down scopes."""

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from sqlalchemy import extract, func, select

from app.domain.investigations.preview import ERRORS
from app.domain.models import (
    CurrentPublication,
    ExceptionPublication,
    LocalOrganisation,
    NMVSException,
    SAIPackage,
    SAIPreparation,
)
from app.portal.exception_queries import apply_trend_scope

SERIES = ("A2", "A3", "A7", "A24", "A52", "A68", "Other")
COLOURS = ("#2367a5", "#08786f", "#8a5cad", "#ad6519", "#a33950", "#4d712c", "#637384")


def alert_link(start, end, **filters):
    return "/exceptions?" + urlencode(
        {
            "start": start,
            "end": end,
            "work_status": "all",
            "tv_exceptions_view": "all",
            **{key: value for key, value in filters.items() if value},
        }
    )


def trends(session, namespace, start, end, alert_group, country):
    alert = NMVSException
    statement = apply_trend_scope(
        select(alert).where(
            alert.source_namespace == namespace,
            alert.alert_at >= datetime.combine(start, time.min),
            alert.alert_at < datetime.combine(end + timedelta(days=1), time.min),
        ),
        alert_group,
        "",
        country,
    )
    year = extract("year", alert.alert_at)
    month = extract("month", alert.alert_at)
    counts = defaultdict(Counter)
    for y, m, code, count in session.execute(
        statement.with_only_columns(
            year, month, alert.error_code, func.count()
        ).group_by(year, month, alert.error_code)
    ):
        counts[date(y, m, 1)][code if code in SERIES[:-1] else "Other"] += count

    intervals = session.execute(
        select(ExceptionPublication.period_start, ExceptionPublication.period_end)
        .where(
            ExceptionPublication.source_namespace == namespace,
            ExceptionPublication.period_start
            < datetime.combine(end + timedelta(days=1), time.min),
            ExceptionPublication.period_end >= datetime.combine(start, time.min),
        )
        .order_by(ExceptionPublication.period_start)
    )
    # Publication windows use inclusive millisecond timestamps.
    merged = []
    for first, last in intervals:
        if merged and first <= merged[-1][1] + timedelta(milliseconds=1):
            merged[-1] = (merged[-1][0], max(merged[-1][1], last))
        else:
            merged.append((first, last))

    filters = {"alert_group": alert_group, "country": country}
    monthly = []
    anchor = start.replace(day=1)
    while anchor <= end:
        following = (anchor.replace(day=28) + timedelta(days=4)).replace(day=1)
        first, last = max(anchor, start), min(following - timedelta(days=1), end)
        covered = sum(
            any(
                a <= datetime.combine(day, time.min)
                and b >= datetime.combine(day, time(23, 59, 59, 999000))
                for a, b in merged
            )
            for day in (
                first + timedelta(days=i) for i in range((last - first).days + 1)
            )
        )
        monthly.append(
            {
                "month": anchor.isoformat()[:7],
                "counts": counts[anchor],
                "total": counts[anchor].total(),
                "covered": covered,
                "days": (last - first).days + 1,
                "url": alert_link(first, last, **filters),
            }
        )
        anchor = following

    def top(field):
        count = func.count()
        return session.execute(
            statement.with_only_columns(field, count)
            .where(field.is_not(None), field != "")
            .group_by(field)
            .order_by(count.desc(), field)
            .limit(5)
        ).all()

    org_top = top(alert.organisation_id)
    product_top = top(alert.gtin14)
    org_names = dict(
        session.execute(
            select(
                LocalOrganisation.source_organisation_id,
                LocalOrganisation.organisation_name,
            ).where(
                LocalOrganisation.source_namespace == namespace,
                LocalOrganisation.source_organisation_id.in_(
                    [identifier for identifier, _ in org_top]
                ),
            )
        ).all()
    )
    product_names = defaultdict(list)
    publication = session.get(CurrentPublication, "product-batch")
    if publication and publication.source_namespace == namespace:
        for code, name in session.execute(
            select(SAIPackage.gtin14, SAIPreparation.preparation_name)
            .join(SAIPreparation, SAIPackage.preparation_id == SAIPreparation.id)
            .where(
                SAIPackage.is_observed == 1,
                SAIPackage.last_mapping_run_id == publication.mapping_run_id,
                SAIPackage.gtin14.in_([identifier for identifier, _ in product_top]),
            )
        ):
            product_names[code].append(name)
    return {
        "monthly": monthly,
        "total": sum(item["total"] for item in monthly),
        "covered": sum(item["covered"] for item in monthly),
        "peak": max((item["total"] for item in monthly), default=0),
        "series": [
            (code, colour, ERRORS[code][0] if code in ERRORS else "Other alert types")
            for code, colour in zip(SERIES, COLOURS, strict=True)
            if any(item["counts"][code] for item in monthly)
        ],
        "organisations": [
            (
                org_names.get(identifier) or f"Organisation {identifier}",
                identifier,
                count,
                alert_link(start, end, organisation=identifier, **filters),
            )
            for identifier, count in org_top
        ],
        "products": [
            (
                product_names[code][0] if len(product_names[code]) == 1 else code,
                code,
                count,
                alert_link(start, end, gtin14=code, **filters),
            )
            for code, count in product_top
        ],
        "alerts_url": alert_link(start, end, **filters),
    }
