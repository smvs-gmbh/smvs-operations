from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import func, select

from app.core.db.models import ProcessingRun
from app.domain.activity.mapping import publish_activity
from app.domain.models import ActivityDay
from app.integration.idempotency import result_run_id
from app.integration.sources.nmvs.activity.acquisition import UserActivityAcquisition
from app.integration.sources.nmvs.activity.api import UserActivityClient
from app.integration.sources.nmvs.connection import reporting_client


def source_namespace(client):
    origin = urlsplit(client._base_url)
    return f"nmvs-origin:{origin.scheme}://{origin.netloc}"


def import_period(factory, client, start, end):
    if end < start or end >= datetime.now(UTC).date() or (end - start).days > 30:
        raise ValueError("Request 1 to 31 complete UTC days at a time.")
    with factory() as session:
        job = UserActivityAcquisition(client).run(session, start, end)
        job_id = job.id
        run = session.scalar(
            select(ProcessingRun)
            .join(ProcessingRun.artifact)
            .where(
                ProcessingRun.artifact.has(integration_job_id=job_id),
                ProcessingRun.status == "succeeded",
            )
            .order_by(ProcessingRun.id.desc())
        )
        run_id = result_run_id(run)
    publication = publish_activity(factory, run_id, source_namespace(client))
    return job_id, publication


def pending_periods(factory, namespace, *, today=None):
    yesterday = (today or datetime.now(UTC).date()) - timedelta(days=1)
    initial = yesterday - timedelta(days=89)
    with factory() as session:
        earliest = session.scalar(
            select(func.min(ActivityDay.activity_date)).where(
                ActivityDay.source_namespace == namespace
            )
        )
        start = min(initial, earliest) if earliest else initial
        coverage = session.execute(
            select(ActivityDay.activity_date, ActivityDay.section).where(
                ActivityDay.source_namespace == namespace,
                ActivityDay.activity_date.between(start, yesterday),
            )
        ).all()
    present = {}
    for d, section in coverage:
        present.setdefault(d, set()).add(section)
    # Always revisit seven recent days to accept late source corrections. Older gaps never disappear.
    needed = [
        start + timedelta(days=i)
        for i in range((yesterday - start).days + 1)
        if present.get(start + timedelta(days=i), set())
        != {"Verification", "IMT Fulfilment"}
        or start + timedelta(days=i) >= yesterday - timedelta(days=6)
    ]
    periods = []
    for day in needed:
        if (
            periods
            and day == periods[-1][1] + timedelta(days=1)
            and (day - periods[-1][0]).days < 30
        ):
            periods[-1] = (periods[-1][0], day)
        else:
            periods.append((day, day))
    return periods


def scheduled_import(factory):
    client = reporting_client(UserActivityClient)
    latest_job = None
    try:
        periods = pending_periods(factory, source_namespace(client))
        for start, end in periods:
            job_id, _ = import_period(factory, client, start, end)
            with factory() as session:
                from app.core.db.models import IntegrationJob

                latest_job = session.get(IntegrationJob, job_id)
                session.expunge(latest_job)
        return latest_job
    finally:
        client.close()
