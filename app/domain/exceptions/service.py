from datetime import UTC, date, datetime, time, timedelta

from app.core.config import get_settings
from app.domain.exceptions.mapping import publish_exceptions
from app.integration.idempotency import result_run_id
from app.integration.sources.nmvs.connection import reporting_client
from app.integration.sources.nmvs.exceptions.acquisition import ExceptionsAcquisition
from app.integration.sources.nmvs.exceptions.api import ExceptionsClient


def client_from_settings():
    settings = get_settings()
    if not settings.nmvs_exceptions_base_url or not settings.nmvs_exceptions_authority:
        raise ValueError(
            "Explicit Exception API origin and national source authority are required."
        )
    return reporting_client(
        ExceptionsClient,
        base_url=settings.nmvs_exceptions_base_url,
        api_version=settings.nmvs_exceptions_api_version,
    )


def import_window(factory, client, start, end, authority):
    with factory() as session:
        job, run = ExceptionsAcquisition(client, authority).run(session, start, end)
        job_id, run_id = job.id, result_run_id(run)
    return job_id, publish_exceptions(factory, run_id, authority)


def import_days(factory, start: date, end: date, *, progress=None):
    settings = get_settings()
    if end < start or end > datetime.now(UTC).date():
        raise ValueError("Invalid exception date range.")
    client = client_from_settings()
    latest = None
    try:
        while start <= end:
            through = min(start + timedelta(days=29), end)
            a = datetime.combine(start, time.min, tzinfo=UTC)
            b = min(
                datetime.combine(through, time(23, 59, 59, 999000), tzinfo=UTC),
                datetime.now(UTC),
            )
            job, pub = import_window(
                factory, client, a, b, settings.nmvs_exceptions_authority
            )
            latest = job
            if progress:
                progress(job, pub)
            start = through + timedelta(days=1)
        return latest
    finally:
        client.close()


def scheduled_import(factory):
    """Cover missed UTC days and refresh seven recent days, including today's partial data."""
    from sqlalchemy import select

    from app.core.db.models import IntegrationJob
    from app.domain.models import ExceptionPublication

    settings = get_settings()
    today = datetime.now(UTC).date()
    start = today - timedelta(days=90)
    with factory() as session:
        publications = session.scalars(
            select(ExceptionPublication).where(
                ExceptionPublication.source_namespace
                == settings.nmvs_exceptions_authority
            )
        ).all()
    if publications:
        start = min(start, min(p.period_start.date() for p in publications))
    covered = set()
    for p in publications:
        day = p.period_start.date()
        while day <= p.period_end.date():
            a = datetime.combine(day, time.min)
            b = datetime.combine(day, time(23, 59, 59, 999000))
            if p.period_start <= a and p.period_end >= b:
                covered.add(day)
            day += timedelta(days=1)
    needed = [
        start + timedelta(days=i)
        for i in range((today - start).days + 1)
        if start + timedelta(days=i) not in covered
        or start + timedelta(days=i) >= today - timedelta(days=6)
    ]
    windows = []
    for d in needed:
        if windows and d == windows[-1][1] + timedelta(days=1):
            windows[-1] = (windows[-1][0], d)
        else:
            windows.append((d, d))
    latest = None
    for a, b in windows:
        latest = import_days(factory, a, b)
    with factory() as session:
        job = session.get(IntegrationJob, latest)
        if job:
            session.expunge(job)
        return job
