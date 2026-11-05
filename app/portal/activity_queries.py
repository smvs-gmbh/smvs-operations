from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.domain.models import (
    ActivityDay,
    ActivityFact,
    ActivityPublication,
    LocalOrganisation,
    ParticipantPublication,
)


def namespace(session):
    # Prefer the namespace selected by the participant publication. Never blend environments.
    participant = session.get(ParticipantPublication, "participants")
    if participant:
        return participant.source_namespace
    return session.scalar(
        select(ActivityPublication.source_namespace)
        .order_by(ActivityPublication.id.desc())
        .limit(1)
    )


def activity(
    session,
    *,
    section,
    start,
    end,
    organisation="",
    market="",
    process="",
    org_type="",
    sort="count",
    day=None,
):
    ns = namespace(session)
    length = (end - start).days + 1
    previous_start, previous_end = (
        start - timedelta(days=length),
        start - timedelta(days=1),
    )
    base = [ActivityFact.source_namespace == ns, ActivityFact.section == section]
    if organisation:
        base.append(ActivityFact.source_organisation_id == organisation)
    if market:
        base.append(ActivityFact.market == market)
    if process:
        base.append(ActivityFact.business_process == process)
    if org_type:
        base.append(ActivityFact.organisation_type == org_type)
    coverage = set(
        session.scalars(
            select(ActivityDay.activity_date).where(
                ActivityDay.source_namespace == ns,
                ActivityDay.section == section,
                ActivityDay.activity_date.between(previous_start, end),
            )
        )
    )
    facts = session.scalars(
        select(ActivityFact).where(
            *base,
            ActivityFact.metric_kind == "transactions",
            ActivityFact.activity_date.between(previous_start, end),
        )
    ).all()
    measurement_query = select(ActivityFact).where(
        *base,
        ActivityFact.metric_kind != "transactions",
        ActivityFact.metric_value != 0,
        ActivityFact.activity_date.between(day or start, day or end),
    )
    measurements = session.scalars(
        measurement_query.order_by(
            ActivityFact.activity_date.desc(), ActivityFact.organisation_name
        ).limit(101)
    ).all()
    daily = defaultdict(lambda: [0, 0])
    current, previous = {}, {}
    per_process = bool(organisation or market)
    orgs = {
        o.source_organisation_id: o
        for o in session.scalars(
            select(LocalOrganisation).where(LocalOrganisation.source_namespace == ns)
        )
    }
    for f in facts:
        daily[f.activity_date][0] += f.transaction_count
        daily[f.activity_date][1] += f.exception_count
        group = (
            f.business_process
            if per_process
            else f.source_organisation_id
            if section == "Verification"
            else f.market
        )
        target = current if start <= f.activity_date <= end else previous
        if day is not None and target is current and f.activity_date != day:
            continue
        if group not in target:
            org = orgs.get(f.source_organisation_id)
            target[group] = {
                "key": group,
                "name": f.business_process
                if per_process
                else (f.organisation_name or group)
                if section == "Verification"
                else f.market,
                "type": f.organisation_type,
                "count": 0,
                "exceptions": 0,
                "organisation_id": org.id if org else None,
            }
        target[group]["count"] += f.transaction_count
        target[group]["exceptions"] += f.exception_count
    days = []
    for i in range(length):
        d = start + timedelta(days=i)
        days.append(
            {
                "date": d,
                "count": daily[d][0] if d in coverage else None,
                "exceptions": daily[d][1] if d in coverage else None,
            }
        )
    maxima = {
        metric: max((d[metric] or 0 for d in days), default=0)
        for metric in ("count", "exceptions")
    }
    for i, d in enumerate(days):
        d["x"] = 56 + (i + 0.5) * 910 / length
        d["width"] = max(1, 910 / length * 0.72)
        step = max(1, (length + 7) // 8)
        d["tick"] = (i % step == 0 and length - 1 - i >= step / 2) or i == length - 1
        for metric in ("count", "exceptions"):
            d[metric + "_height"] = (d[metric] or 0) / max(1, maxima[metric]) * 120
    covered = sum(d["count"] is not None for d in days)
    complete = covered == length
    previous_complete = all(
        previous_start + timedelta(days=i) in coverage for i in range(length)
    )
    total = sum(d["count"] or 0 for d in days)
    exceptions = sum(d["exceptions"] or 0 for d in days)
    previous_total = sum(
        daily[previous_start + timedelta(days=i)][0] for i in range(length)
    )
    comparison = (
        (total / previous_total - 1) * 100
        if complete and previous_complete and previous_total
        else None
    )
    if complete and day is None:
        for group, prior in previous.items():
            if group not in current:
                current[group] = {**prior, "count": 0, "exceptions": 0}
    for row in current.values():
        before = previous.get(row["key"], {}).get("count", 0)
        row["delta"] = (
            (row["count"] / before - 1) * 100
            if complete and previous_complete and before and day is None
            else None
        )
        row["rate"] = row["exceptions"] / row["count"] * 100 if row["count"] else None
    sort_key = {
        "count": "count",
        "exceptions": "exceptions",
        "name": "name",
        "rate": "rate",
        "delta": "delta",
    }[sort]
    rows = sorted(
        current.values(),
        key=lambda r: (
            r[sort_key] is not None,
            r[sort_key] if r[sort_key] is not None else -float("inf"),
        ),
        reverse=sort != "name",
    )
    options = session.execute(
        select(
            ActivityFact.source_organisation_id,
            ActivityFact.organisation_name,
            ActivityFact.organisation_type,
            ActivityFact.market,
            ActivityFact.business_process,
        )
        .where(ActivityFact.source_namespace == ns, ActivityFact.section == section)
        .distinct()
    ).all()
    # IDs retain source spelling, names are report-observed values.
    entities = (
        {r[0]: r[1] for r in options if r[0]}
        if section == "Verification"
        else {r[3]: r[3] for r in options if r[3]}
    )
    all_days = set(
        session.scalars(
            select(ActivityDay.activity_date).where(
                ActivityDay.source_namespace == ns, ActivityDay.section == section
            )
        )
    )
    latest = max(all_days) if all_days else None
    first = min(all_days) if all_days else None
    contiguous = first
    while contiguous and contiguous + timedelta(days=1) in all_days:
        contiguous += timedelta(days=1)
    return {
        "selected_day_covered": day in coverage if day else bool(covered),
        "activity_section": True,
        "publication": None,
        "source_namespace": ns,
        "rows": rows,
        "days": days,
        "total": total,
        "exceptions": exceptions,
        "rate": exceptions / total * 100 if total else None,
        "covered": covered,
        "expected": length,
        "complete": complete,
        "previous_complete": previous_complete,
        "comparison": comparison,
        "previous_start": previous_start,
        "previous_end": previous_end,
        "maxima": maxima,
        "entities": sorted(entities.items(), key=lambda r: r[1] or ""),
        "processes": sorted(
            {
                r[4]
                for r in options
                if not r[4].endswith((" - Avg. No. Packs", " - Total No. Packs"))
            }
        ),
        "types": sorted({r[2] for r in options}),
        "measurements": measurements[:100],
        "more_measurements": len(measurements) > 100,
        "latest": latest,
        "first": first,
        "contiguous": contiguous,
        "per_process": per_process,
        "yesterday": datetime.now(UTC).date() - timedelta(days=1),
    }
