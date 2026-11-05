from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select

from app.core.db.models import AcquiredArtifact
from app.core.db.session import SessionFactory
from app.domain.mapping import key
from app.domain.models import UploadReport, UploadRequest
from app.domain.uploads import service
from app.integration.sources.nmvs.exceptions.parsing import source_time
from app.integration.sources.nmvs.pack_audit.parsing import details, scheme
from app.integration.sources.nmvs.parsing import record_hash
from app.integration.sources.nmvs.uploads.parsing import instant
from app.integration.sources.sai.parsing import normalize_gtin14
from app.portal import exception_queries
from app.portal.exception_routes import current, exception_record_navigation
from app.portal.pack_audit_routes import state as pack_audit_state
from app.portal.routes import DbSession, templates

router = APIRouter()
LABELS = {
    "ReceivedValidPpdMessage": "Upload request received",
    "PpdNewBatchCreated": "New batch created",
    "ProcessedSuccessfulPpdCreateMessage": "Upload processed",
    "PpdInsufficientRandomizationOfSerialNumbers": "Insufficient serial number randomisation (A54)",
    "Alert": "Alert dispatch recorded",
}


ONE_DAY = timedelta(days=1)
LOOKBACK_DAYS = 90


def pack_creation(session, record):
    batch = record.stored_batch or record.provided_batch
    if not batch:
        return None
    try:
        _, report, _ = pack_audit_state(session, record)
    except HTTPException as exc:
        if exc.status_code == 409:
            return None
        raise
    if not report:
        return None
    dates = {
        source_time(row.get("Date and Time (UTC)"))[0]
        for row in report.events_json
        if row.get("Event Name") == "PpdNewPackCreated"
        and row.get("Batch Number") == batch
    }
    return next(iter(dates)) if len(dates) == 1 else None


def midnight(day):
    return datetime.combine(day, datetime.min.time())


def suggestion_bounds(record, creation, yesterday):
    if creation and creation.date() <= yesterday:
        return creation.date() - ONE_DAY, min(creation.date() + ONE_DAY, yesterday)
    alert_day = min(record.alert_at.date(), yesterday) if record.alert_at else yesterday
    end = min(alert_day + ONE_DAY, yesterday)
    return end - timedelta(days=LOOKBACK_DAYS - 1), end


def period(record, start, end, *, creation=None):
    yesterday = datetime.now(UTC).date() - ONE_DAY
    default_start, default_end = suggestion_bounds(record, creation, yesterday)
    default_start = max(default_start, default_end - timedelta(days=30))
    start = start or default_start
    end = end or default_end
    if start > end or (end - start).days >= 31 or end > yesterday:
        raise HTTPException(422, "Select 1 to 31 complete UTC calendar days.")
    return midnight(start), midnight(end + ONE_DAY)


def suggested_gap(reports, start, end, *, prefer=None):
    """One contiguous gap of at most 31 complete calendar days."""
    missing = [
        start + timedelta(days=i)
        for i in range((end - start).days + 1)
        if not service.covered(
            reports,
            midnight(start + timedelta(days=i)),
            midnight(start + timedelta(days=i + 1)),
        )
    ]
    if not missing:
        return None
    last = (
        min(missing, key=lambda day: (abs(day - prefer), day))
        if prefer
        else missing[-1]
    )
    first = last
    uncovered = set(missing)
    while first - ONE_DAY in uncovered and (last - first).days < 30:
        first -= ONE_DAY
    while last + ONE_DAY in uncovered and (last - first).days < 30:
        last += ONE_DAY
    return first, last


def product_identity(code_scheme, code):
    family = scheme(code_scheme)
    if not family or not code:
        return None
    if family == "GTIN":
        try:
            normalized = normalize_gtin14(code)
        except ValueError:
            return None
        return (family, normalized) if normalized else None
    return family, code


def evidence(session, record, start, end, *, include_outside=False):
    statement = select(
        UploadReport.id,
        UploadReport.period_start,
        UploadReport.period_end,
        UploadReport.captured_at,
    ).where(UploadReport.source_namespace == record.source_namespace)
    if not include_outside:
        statement = statement.where(
            UploadReport.period_start < end, UploadReport.period_end > start
        )
    # Keep only small report metadata in memory. Load event JSON one report at a time.
    reports = list(session.execute(statement))
    # Sorting large JSON values in MySQL can exhaust the server sort buffer.
    reports.sort(key=lambda r: (r.captured_at, r.id), reverse=True)
    identity = product_identity(record.product_code_scheme, record.product_code)
    batches = {b for b in (record.provided_batch, record.stored_batch) if b}
    rows, seen, outside = [], set(), {}
    identities = {}
    for report in reports:
        if not identity or not batches:
            break
        events = session.scalar(
            select(UploadReport.events_json).where(UploadReport.id == report.id)
        )
        for row in events:
            product = (row.get("Product Code Scheme"), row.get("Product Code"))
            if product not in identities:
                identities[product] = product_identity(*product)
            if identities[product] != identity:
                continue
            d = details(row.get("Event Details"))
            if d.get("BatchId") not in batches:
                continue
            at = instant(row["Date and Time (UTC)"])
            digest = record_hash(row)
            if digest in seen:
                continue
            seen.add(digest)
            if not start <= at < end:
                # Source reports have inclusive endpoints. Do not turn the boundary
                # of an imported window into evidence about a future/incomplete day.
                if not include_outside or at.date() >= datetime.now(UTC).date():
                    continue
                bucket_key = (at.date(), d["BatchId"])
                bucket = outside.setdefault(
                    bucket_key,
                    {
                        "day": at.date(),
                        "batch": d["BatchId"],
                        "count": 0,
                        "batch_role": "Provided & Stored"
                        if record.provided_batch == record.stored_batch
                        else "Provided"
                        if d["BatchId"] == record.provided_batch
                        else "Stored",
                    },
                )
                bucket["count"] += 1
                continue
            rows.append(
                {
                    "at": at,
                    "label": LABELS.get(row["Event Name"], row["Event Name"]),
                    "raw": row,
                    "report_id": report.id,
                    "batch": d.get("BatchId"),
                    "batch_role": "Provided & Stored"
                    if record.provided_batch == record.stored_batch
                    else "Provided"
                    if d.get("BatchId") == record.provided_batch
                    else "Stored",
                    "requested": d.get("NumberOfPacksInRequest"),
                    "successful": d.get("NumberOfPacksSuccessfullyUploaded"),
                    "unsuccessful": d.get("NumberOfUnsuccessfulPackUploads"),
                    "version": d.get("ProductVersion"),
                    "after_alert": record.alert_at is not None and at > record.alert_at,
                }
            )
    rows.sort(key=lambda r: (r["at"], r["raw"]["Event Name"]))
    return {
        "rows": rows,
        "covered": service.covered(reports, start, end),
        "outside": sorted(
            outside.values(), key=lambda b: (b["day"], b["batch"]), reverse=True
        ),
        "eligible": bool(identity and batches),
        "coverage_reports": reports,
        "reports": [
            r for r in reports if r.period_start < end and r.period_end > start
        ],
    }


@router.get("/exceptions/{identifier}/uploads", include_in_schema=False)
def uploads(
    request: Request,
    identifier: int,
    session: DbSession,
    start: date | None = None,
    end: date | None = None,
    page: int = Query(1, ge=1, le=10000),
    history_page: int = Query(1, ge=1, le=10000),
):
    record = current(session, identifier)
    creation = pack_creation(session, record)
    yesterday = datetime.now(UTC).date() - ONE_DAY
    anchor = creation if creation and creation.date() <= yesterday else None
    first, last = period(record, start, end, creation=anchor)
    result = evidence(session, record, first, last, include_outside=True)
    expected_batch = record.stored_batch or record.provided_batch
    selected_match = any(row["batch"] == expected_batch for row in result["rows"])
    matches = [row for row in result["outside"] if row["batch"] == expected_batch]
    reference_day = (
        anchor.date()
        if anchor
        else record.alert_at.date()
        if record.alert_at
        else yesterday
    )
    recommended = (
        min(
            matches,
            key=lambda row: (
                abs(row["day"] - reference_day)
                if anchor
                else row["day"] > reference_day,
                abs(row["day"] - reference_day),
                row["day"],
            ),
        )
        if matches and not selected_match
        else None
    )
    search_start, search_end = suggestion_bounds(record, anchor, yesterday)
    gap = None
    if result["eligible"] and not selected_match and not recommended:
        recent_start = max(search_start, search_end - timedelta(days=30))
        gap = suggested_gap(
            result["coverage_reports"],
            recent_start,
            search_end,
            prefer=anchor.date() if anchor else None,
        )
        if not gap and search_start < recent_start:
            gap = suggested_gap(
                result["coverage_reports"], search_start, recent_start - ONE_DAY
            )
    outside = result["outside"]
    history_pages = max(1, (len(outside) + 9) // 10)
    history_page = min(history_page, history_pages)
    task = session.scalar(
        select(UploadRequest).where(
            UploadRequest.request_key
            == key(
                record.source_namespace, first.isoformat(), last.isoformat(), "genuine"
            )
        )
    )
    pages = max(1, (len(result["rows"]) + 49) // 50)
    page = min(page, pages)
    return templates.TemplateResponse(
        request=request,
        name="uploads.html",
        context={
            "record_nav": exception_record_navigation(request, session, record)
            if record
            else None,
            **exception_queries.context(session),
            **result,
            "upload_section": True,
            "record": record,
            "title": "Upload history",
            "active": "exceptions",
            "task": task,
            "total": len(result["rows"]),
            "outside_total": len(outside),
            "outside": outside[(history_page - 1) * 10 : history_page * 10],
            "history_page": history_page,
            "history_pages": history_pages,
            "rows": result["rows"][(page - 1) * 50 : page * 50],
            "page": page,
            "pages": pages,
            "start": first.date(),
            "end": (last - timedelta(days=1)).date(),
            "yesterday": yesterday,
            "creation": creation,
            "anchor": anchor,
            "expected_batch": expected_batch,
            "recommended": recommended,
            "gap": gap,
            "search_start": search_start,
            "search_end": search_end,
            "selected_match": selected_match,
        },
    )


@router.post("/exceptions/{identifier}/uploads", include_in_schema=False)
def request_upload(
    request: Request,
    identifier: int,
    session: DbSession,
    start: date,
    end: date,
    refresh: bool = False,
):
    origin = urlsplit(str(request.url))
    if request.headers.get("origin") != f"{origin.scheme}://{origin.netloc}":
        raise HTTPException(403, "Request the report from the local detail view.")
    record = current(session, identifier)
    first, last = period(record, start, end)
    if not product_identity(record.product_code_scheme, record.product_code) or not (
        record.provided_batch or record.stored_batch
    ):
        raise HTTPException(422, "Product code or batch is missing or invalid.")
    result = evidence(session, record, first, last)
    if not result["covered"] or refresh:
        service.request_report(
            SessionFactory, record.source_namespace, first, last, refresh=refresh
        )
    return RedirectResponse(
        f"/exceptions/{identifier}/uploads?start={start}&end={end}", status_code=303
    )


@router.get("/upload-reports/{report_id}/original", include_in_schema=False)
def original(report_id: int, session: DbSession):
    report = session.get(UploadReport, report_id)
    if not report or report.source_namespace != exception_queries.namespace(session):
        raise HTTPException(404, "Report not found.")
    artifact = session.get(AcquiredArtifact, report.acquired_artifact_id)
    return Response(
        artifact.artifact_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="pack-upload-{report.id}.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
