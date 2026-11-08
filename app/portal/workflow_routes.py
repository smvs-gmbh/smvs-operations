"""Internal workflows for preparing and reviewing self-declaration invitations."""

import re
from collections import Counter

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.crm.declaration_workflow import (
    FORM_URL,
    candidates,
    create_drafts,
    invitation_url,
    unique_emails,
    usable_email,
)
from app.domain.models import CRMDeclarationDraft, CRMMah, CRMSelfDeclaration
from app.integration.artifacts.storage import utcnow
from app.portal.exception_routes import review_form
from app.portal.record_navigation import list_record_navigation
from app.portal.routes import DbSession, templates

router = APIRouter()
PATH = "/workflows/self-declarations"


def data_year(value):
    if not re.fullmatch(r"[0-9]{4}", value) or not 1900 <= int(value) <= utcnow().year:
        raise HTTPException(422, "Choose a current or previous data year.")
    return int(value)


def invitation_secret():
    configured = get_settings().declaration_invitation_secret
    return configured.get_secret_value() if configured else None


def draft_form_url(request, draft, mah, secret):
    form_url = getattr(request.app.state, "declaration_form_url", FORM_URL)
    return invitation_url(draft, mah, secret, form_url=form_url)


@router.get("/workflows", include_in_schema=False)
def workflows():
    return RedirectResponse(PATH)


def previous_cycle(session, year, eligible):
    rows = session.execute(
        select(CRMSelfDeclaration, CRMMah.name)
        .outerjoin(CRMMah, CRMMah.id == CRMSelfDeclaration.mah_id)
        .where(CRMSelfDeclaration.declaration_year == year - 1)
        .order_by(CRMSelfDeclaration.record_label, CRMSelfDeclaration.id)
    ).all()
    statuses = Counter(item.status for item, _ in rows)
    prior = {item.mah_id: name for item, name in rows if item.mah_id is not None}
    current = {item.mah.id for item in eligible}
    return {
        "total": len(rows),
        "sent": statuses["Selfdeclaration sent"],
        "progressed": sum(
            statuses[status]
            for status in (
                "Selfdeclaration received",
                "Pro-forma invoice created",
                "Invoice created",
                "Invoice sent",
            )
        ),
        "statuses": sorted(
            ((status or "No status", count) for status, count in statuses.items())
        ),
        "unassigned": [item for item, _ in rows if item.mah_id is None],
        "added": [item.mah for item in eligible if item.mah.id not in prior],
        "removed": sorted(
            (
                (identifier, name)
                for identifier, name in prior.items()
                if identifier not in current
            ),
            key=lambda pair: pair[1].casefold(),
        ),
    }


@router.get(PATH, include_in_schema=False)
def declaration_workflow(
    request: Request, session: DbSession, year: str = Query("", max_length=4)
):
    selected_year = data_year(year or str(utcnow().year))
    rows = candidates(session, selected_year)
    drafts = session.execute(
        select(CRMDeclarationDraft, CRMMah.name)
        .join(CRMMah, CRMMah.id == CRMDeclarationDraft.mah_id)
        .where(CRMDeclarationDraft.data_year == selected_year)
        .order_by(CRMMah.name, CRMDeclarationDraft.id)
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="declaration_workflow.html",
        context={
            "title": "Prepare self-declarations",
            "active": "workflows",
            "year": selected_year,
            "candidates": rows,
            "previous": previous_cycle(session, selected_year, rows),
            "drafts": drafts,
            "has_new": any(not item.existing for item in rows),
            "configured": bool(invitation_secret()),
        },
    )


@router.post(PATH, include_in_schema=False)
async def prepare_declarations(request: Request, session: DbSession):
    data = await review_form(request)
    year = data_year(data.get("year", ""))
    secret = invitation_secret()
    if not secret:
        raise HTTPException(503, "Configure the declaration invitation secret first.")
    create_drafts(session, year, secret)
    session.commit()
    return RedirectResponse(f"{PATH}?year={year}#drafts", status_code=303)


def get_draft(session, identifier, *, lock=False):
    draft = session.get(CRMDeclarationDraft, identifier, with_for_update=lock)
    if draft is None:
        raise HTTPException(404, "Declaration draft not found.")
    return draft


@router.get(PATH + "/{identifier}", include_in_schema=False)
def declaration_draft(request: Request, identifier: int, session: DbSession):
    draft = get_draft(session, identifier)
    mah = session.get(CRMMah, draft.mah_id)
    secret = invitation_secret()
    link = draft_form_url(request, draft, mah, secret) if secret else None
    eligible = candidates(session, draft.data_year, mah_id=draft.mah_id)
    recipient_options = eligible[0].recipient_options if eligible else ()
    year_query = f"?year={draft.data_year}"
    navigation = list_record_navigation(
        session,
        select(CRMDeclarationDraft)
        .join(CRMMah, CRMMah.id == CRMDeclarationDraft.mah_id)
        .where(CRMDeclarationDraft.data_year == draft.data_year),
        CRMDeclarationDraft.id,
        identifier,
        (CRMMah.name, CRMDeclarationDraft.id),
        PATH,
        "Review drafts",
        back_query=f"{year_query}#drafts",
    )
    return templates.TemplateResponse(
        request=request,
        name="declaration_draft.html",
        context={
            "title": "Review declaration draft",
            "active": "workflows",
            "draft": draft,
            "mah": mah,
            "invitation_url": link,
            "test_workspace": getattr(request.app.state, "test_workspace", False),
            "record_nav": navigation,
            "recipient_options": recipient_options,
        },
        headers={"Cache-Control": "no-store", "Referrer-Policy": "same-origin"},
    )


@router.post(PATH + "/{identifier}", include_in_schema=False)
async def update_declaration_draft(
    request: Request, identifier: int, session: DbSession
):
    data = await review_form(request)
    draft = get_draft(session, identifier, lock=True)
    command = data.get("command")
    if command == "reopen" and draft.approved_at:
        draft.approved_at = draft.approved_by = None
    elif command in ("save", "approve") and draft.approved_at is None:
        raw_recipients = data.get("recipient_emails", data.get("recipient_email", ""))
        recipients = unique_emails(
            value.strip()
            for value in re.split(r"[,\n]", raw_recipients)
            if value.strip()
        )
        if len(recipients) > 1000 or any(
            not usable_email(address) for address in recipients
        ):
            raise HTTPException(422, "Enter valid recipient email addresses.")
        if command == "approve":
            if not recipients:
                raise HTTPException(
                    422,
                    "At least one recipient email address is required for approval.",
                )
            if not candidates(session, draft.data_year, mah_id=draft.mah_id):
                raise HTTPException(
                    409, "This MAH no longer meets the preparation criteria."
                )
            secret = invitation_secret()
            if not secret or not draft_form_url(
                request, draft, session.get(CRMMah, draft.mah_id), secret
            ):
                raise HTTPException(409, "The invitation link cannot be verified.")
            draft.approved_at = utcnow()
            draft.approved_by = getattr(
                getattr(request.state, "portal_user", None), "email", None
            )
        draft.recipient_emails = recipients
    else:
        raise HTTPException(409, "This draft changed. Reload it before continuing.")
    session.commit()
    return RedirectResponse(f"{PATH}/{identifier}", status_code=303)
