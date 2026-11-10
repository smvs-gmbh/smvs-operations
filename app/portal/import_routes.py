from datetime import date
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.core.db.session import SessionFactory
from app.integration.scheduler.control import SOURCES, cancel, enqueue
from app.integration.scheduler.handlers import default_handlers
from app.integration.scheduler.service import ImportScheduler
from app.portal.import_queries import overview
from app.portal.routes import DbSession, templates

router = APIRouter()
NOTICES = {
    "configured": "Cadence saved. The current Scheduled/Paused setting was preserved.",
    "paused": "Automatic starts paused. Running imports will finish. Manual requests remain available.",
    "resumed": "Automatic starts resumed. The next run has been recalculated.",
    "queued": "Import request queued for the worker. This does not start the scheduler. Repeated clicks reuse the same pending request.",
    "busy": "An import for this source is already recorded as running. No duplicate request was queued.",
    "cancelled": "Queued request cancelled.",
}


def guard(request):
    origin = urlsplit(str(request.url))
    if request.headers.get("origin") != f"{origin.scheme}://{origin.netloc}":
        raise HTTPException(
            403, "Use the local Imports page to change or start imports."
        )


def known(key):
    if key not in SOURCES:
        raise HTTPException(404, "Import source not found.")


async def form_values(request):
    guard(request)
    if (
        request.headers.get("content-type", "").split(";", 1)[0]
        != "application/x-www-form-urlencoded"
    ):
        raise HTTPException(415, "Use the import form.")
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > 8192:
            raise HTTPException(413, "Import form is too large.")
    try:
        values = parse_qs(
            body.decode("utf-8"), keep_blank_values=True, max_num_fields=12
        )
    except (ValueError, UnicodeError):
        raise HTTPException(422, "Invalid import form.") from None
    if any(len(v) != 1 for v in values.values()):
        raise HTTPException(422, "Duplicate form fields are not supported.")
    return {k: v[0] for k, v in values.items()}


def redirect(notice):
    return RedirectResponse("/imports?notice=" + notice, status_code=303)


@router.get("/imports", include_in_schema=False)
def imports(
    request: Request,
    session: DbSession,
    source: str = Query("", max_length=100),
    notice: str = "",
):
    if source:
        known(source)
    return render_imports(request, session, source=source, notice=notice)


def render_imports(request, session, *, source="", notice="", backfill_error=None):
    return templates.TemplateResponse(
        request=request,
        name="imports.html",
        status_code=422 if backfill_error else 200,
        context={
            **overview(session, source=source),
            "title": "Imports",
            "active": "imports",
            "imports_section": True,
            "notice": NOTICES.get(notice),
            "backfill_error": backfill_error,
        },
    )


@router.post("/imports/{key}/configure", include_in_schema=False)
async def configure(request: Request, key: str):
    known(key)
    values = await form_values(request)
    mode = values.get("mode")
    if mode not in ("daily", "interval"):
        raise HTTPException(422, "Choose Daily or Interval cadence.")
    try:
        hours = int(values.get("hours", "0")) if mode == "interval" else None
        if hours is not None and not 1 <= hours <= 168:
            raise ValueError("Choose an interval from 1 to 168 hours.")
        from sqlalchemy import select

        from app.core.db.models import ImportSchedule

        with SessionFactory() as s:
            existing = s.scalar(
                select(ImportSchedule).where(ImportSchedule.import_key == key)
            )
            zone = existing.timezone if existing else "Europe/Zurich"
            wall = (
                values.get("daily_time", "")
                if mode == "daily"
                else existing.daily_time
                if existing
                else SOURCES[key]["time"]
            )
        ImportScheduler(SessionFactory, default_handlers()).configure(
            key,
            daily_time=wall,
            timezone=zone,
            enabled=None,
            interval_seconds=hours * 3600 if hours is not None else None,
        )
    except ValueError:
        raise HTTPException(
            422,
            "Cadence could not be saved. Use HH:MM or 1–168 hours; wait for any running import to finish.",
        ) from None
    return redirect("configured")


@router.post("/imports/{key}/pause", include_in_schema=False)
def pause(request: Request, key: str):
    guard(request)
    known(key)
    try:
        ImportScheduler(SessionFactory, default_handlers()).set_enabled(key, False)
    except ValueError:
        raise HTTPException(422, "Configure this import first.") from None
    return redirect("paused")


@router.post("/imports/{key}/resume", include_in_schema=False)
def resume(request: Request, key: str):
    guard(request)
    known(key)
    try:
        ImportScheduler(SessionFactory, default_handlers()).set_enabled(key, True)
    except ValueError:
        raise HTTPException(422, "Configure this import first.") from None
    return redirect("resumed")


@router.post("/imports/{key}/run", include_in_schema=False)
def run_now(request: Request, key: str):
    guard(request)
    known(key)
    try:
        task = enqueue(SessionFactory, key)
    except ValueError:
        raise HTTPException(422, "Configure this import first.") from None
    return redirect("queued" if task else "busy")


@router.post("/imports/{key}/backfill", include_in_schema=False)
async def backfill(request: Request, key: str, session: DbSession):
    known(key)
    values = await form_values(request)
    end_value = values.get("end", "")
    try:
        start = date.fromisoformat(values.get("start", ""))
        end = (
            date.fromisoformat(end_value)
            if end_value and key != "daily_snapshot"
            else start
        )
    except ValueError:
        error = "Enter a valid start date and, if needed, a valid end date."
    else:
        try:
            enqueue(SessionFactory, key, kind="backfill", start=start, end=end)
        except ValueError as exc:
            error = str(exc)
        else:
            return redirect("queued")
    return render_imports(
        request,
        session,
        backfill_error={
            "key": key,
            "message": error,
            "start": values.get("start", ""),
            "end": end_value,
        },
    )


@router.post("/imports/requests/{identifier}/cancel", include_in_schema=False)
def cancel_request(request: Request, identifier: int):
    guard(request)
    try:
        cancel(SessionFactory, identifier)
    except ValueError:
        raise HTTPException(409, "Only queued requests can be cancelled.") from None
    return redirect("cancelled")
