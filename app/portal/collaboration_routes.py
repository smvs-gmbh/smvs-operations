"""Internal evidence preparation and preview; no public participant access."""

from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.core.db.session import SessionFactory
from app.domain.investigations.prechecks import collect
from app.domain.investigations.preview import participant_projection
from app.domain.pack_audit.service import request_report
from app.portal import exception_queries
from app.portal.exception_routes import current, review_form
from app.portal.routes import DbSession, templates

router = APIRouter()


@router.get("/exceptions/{identifier}/participant-preview", include_in_schema=False)
def participant_preview(
    request: Request,
    identifier: int,
    session: DbSession,
    workflow: Literal["pharmacy", "wholesaler"] = "pharmacy",
):
    actor = getattr(request.state, "portal_user", None)
    if not actor or not (
        getattr(actor, "is_nmvo", False) or getattr(actor, "is_admin", False)
    ):
        raise HTTPException(
            403, "An NMVO account is required to review participant previews."
        )
    record = current(session, identifier)
    view = exception_queries.enriched(session, [record])[0]
    prechecks = collect(session, record)
    repeat = prechecks["repeat"]
    preview = participant_projection(
        record,
        name=view["name"],
        holder=view["holder"],
        workflow=workflow,
        repeat=repeat,
        batches=prechecks["batch_references"],
    )
    return templates.TemplateResponse(
        request=request,
        name="participant_preview.html",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        context={
            "title": "Participant preview",
            "active": "exceptions",
            "identifier": record.id,
            "source_version": record.payload_hash,
            "preview": preview,
            "prechecks": prechecks,
            "source_changed": bool(
                view["review"]
                and view["review"].basis_payload_hash != record.payload_hash
            ),
            "intermarket_review": record.is_intermarket != 0
            or record.source_market not in {"CH", "LI"},
            "source_report_id": repeat["report_id"] if repeat else None,
        },
    )


@router.post("/exceptions/{identifier}/prepare-evidence", include_in_schema=False)
async def prepare_evidence(
    request: Request,
    identifier: int,
    session: DbSession,
    target: Literal["analysis", "participant-preview"] = "analysis",
    workflow: Literal["pharmacy", "wholesaler"] = "pharmacy",
):
    actor = getattr(request.state, "portal_user", None)
    if not actor or not (
        getattr(actor, "is_nmvo", False) or getattr(actor, "is_admin", False)
    ):
        raise HTTPException(
            403, "An NMVO account is required to prepare investigation evidence."
        )
    origin = urlsplit(str(request.url))
    if request.headers.get("origin") != f"{origin.scheme}://{origin.netloc}":
        raise HTTPException(403, "Prepare evidence from the local investigation page.")
    record = current(session, identifier)
    data = await review_form(request)
    if data.get("source_version") != record.payload_hash:
        raise HTTPException(
            409, "Source data changed. Review the current pre-checks first."
        )
    plan = collect(session, record)["report_plan"]
    if plan["action"] == "request":
        try:
            await run_in_threadpool(request_report, SessionFactory, identifier)
        except ValueError:
            raise HTTPException(
                422,
                "The pack request could not be prepared. Review the current identifiers.",
            ) from None
    elif plan["action"] not in {"reuse", "pending"}:
        raise HTTPException(409, plan["reason"])
    suffix = f"?workflow={workflow}" if target == "participant-preview" else ""
    return RedirectResponse(
        f"/exceptions/{identifier}/{target}{suffix}", status_code=303
    )
