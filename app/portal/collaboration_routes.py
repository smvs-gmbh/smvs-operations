"""Internal evidence preparation, preview and local pilot access management."""

import os
import re
from collections import defaultdict
from hashlib import sha256
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.alert_desk.schema import CAPA, COMPARISON, FINDINGS
from app.alert_desk.web import ASSETS, DESIGN_ASSETS, DESIGN_STYLES, render_case
from app.core.config import get_settings
from app.core.db.session import SessionFactory
from app.domain.investigations import (
    access,
    audience,
    case_updates,
    pilot,
    pilot_mail,
    rca,
    responses,
)
from app.domain.investigations.prechecks import collect
from app.domain.investigations.preview import ERRORS, participant_projection
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskCaseUpdate,
    AlertDeskEvent,
    AlertDeskGrant,
    AlertDeskResponseRequest,
    AlertDeskSettings,
    CRMContact,
    ExceptionReview,
    NMVSException,
)
from app.domain.pack_audit.service import request_report
from app.portal import exception_queries
from app.portal.exception_routes import current, review_form
from app.portal.routes import DbSession, templates

router = APIRouter()


def require_alert_desk_admin(request):
    actor = getattr(request.state, "portal_user", None)
    if not actor or not getattr(actor, "is_admin", False):
        raise HTTPException(403, "Only administrators can change Alert Desk settings.")


@router.get("/admin/alert-desk", include_in_schema=False)
def alert_desk_settings(request: Request, session: DbSession):
    require_alert_desk_admin(request)
    return templates.TemplateResponse(
        request=request,
        name="alert_desk_settings.html",
        context={
            "title": "Alert Desk settings",
            "active": "alert_desk_settings",
            "response_days": responses.settings_days(session),
        },
    )


@router.post("/admin/alert-desk", include_in_schema=False)
async def save_alert_desk_settings(request: Request, session: DbSession):
    require_alert_desk_admin(request)
    form = await review_form(request, expected_origin=get_settings().portal_auth_origin)
    raw = form.get("response_days", "")
    if not re.fullmatch(r"[0-9]{1,2}", raw) or not 1 <= int(raw) <= 30:
        raise HTTPException(422, "Enter between 1 and 30 working days.")
    settings = session.get(AlertDeskSettings, 1, with_for_update=True)
    if settings is None:
        settings = AlertDeskSettings(id=1)
        session.add(settings)
    settings.response_days = int(raw)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            409, "The settings changed. Reload and try again."
        ) from None
    return RedirectResponse("/admin/alert-desk?saved=yes", status_code=303)


@router.get("/exceptions/{identifier}/participant-preview", include_in_schema=False)
def participant_preview(
    request: Request,
    identifier: int,
    session: DbSession,
    workflow: Literal["pharmacy", "wholesaler"] = "pharmacy",
):
    if pilot_enabled() and request.query_params.get("evidence") != "yes":
        return RedirectResponse(
            f"/exceptions/{identifier}/invitations", status_code=303
        )
    return render_preview(request, identifier, session, workflow)


def render_preview(request, identifier, session, workflow):
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
    suffix = (
        f"?workflow={workflow}&evidence=yes" if target == "participant-preview" else ""
    )
    return RedirectResponse(
        f"/exceptions/{identifier}/{target}{suffix}", status_code=303
    )


def pilot_enabled():
    return (
        (get_settings().environment == "development" or (
            get_settings().environment == "test" and get_settings().alert_desk_test_enabled
        ))
        and len(os.environ.get("ALERT_DESK_PILOT_SECRET", "")) >= 32
    )


templates.env.globals["alert_desk_pilot_enabled"] = pilot_enabled


def pilot_context(session, record, view):
    grants = session.scalars(
        select(AlertDeskGrant)
        .where(AlertDeskGrant.exception_id == record.id)
        .order_by(AlertDeskGrant.id.desc())
    ).all()
    events = (
        session.execute(
            select(AlertDeskEvent)
            .join(AlertDeskGrant, AlertDeskGrant.id == AlertDeskEvent.grant_id)
            .where(AlertDeskGrant.exception_id == record.id)
            .order_by(AlertDeskEvent.id.desc())
        )
        .scalars()
        .all()
    )
    return {
        "pilot_eligible": pilot.in_scope(
            record, view["organisation"], view["location"]
        ),
        "pilot_grants": grants,
        "pilot_events": events,
        "pilot_now": pilot.now(),
        "pilot_labels": {"finding": FINDINGS, "comparison": COMPARISON, "capa": CAPA},
    }


async def pilot_form(request):
    return require_invitation_staff(request), await review_form(
        request, expected_origin=get_settings().portal_auth_origin
    )


@router.post(
    "/exceptions/{identifier}/invitations/revoke/{grant_id}",
    include_in_schema=False,
)
async def revoke_pilot_invitation(
    request: Request,
    identifier: int,
    grant_id: int,
    session: DbSession,
    role: Literal["end_user", "mah"] = "end_user",
):
    actor, _ = await pilot_form(request)
    current(session, identifier)
    grant = session.scalar(
        select(AlertDeskGrant)
        .where(AlertDeskGrant.id == grant_id, AlertDeskGrant.exception_id == identifier)
        .with_for_update()
    )
    if not grant:
        raise HTTPException(404, "Invitation not found.")
    if not grant.revoked_at:
        grant.revoked_at = pilot.now()
        grant.invite_hash = grant.session_hash = None
        pilot.append_event(session, grant, "Access revoked", actor=actor.id)
        session.commit()
    return RedirectResponse(
        f"/exceptions/{identifier}/invitations?role={role}", status_code=303
    )


InvitationRole = Literal["end_user", "mah"]


def require_invitation_staff(request):
    if not pilot_enabled():
        raise HTTPException(404, "Alert Desk pilot is disabled.")
    actor = getattr(request.state, "portal_user", None)
    if not actor or not (actor.is_nmvo or actor.is_admin):
        raise HTTPException(403, "An NMVO account is required.")
    return actor


def render_invitations(request, session, record, role):
    if record.source_market == "LI":
        role = "end_user"
    view = exception_queries.enriched(session, [record])[0]
    return templates.TemplateResponse(
        request=request,
        name="alert_desk_invitations.html",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        context={
            "title": "Participant case preview",
            "active": "exceptions",
            "identifier": record.id,
            "record": record,
            "role": role,
            "case_update": case_updates.latest_update(session, record),
            "can_conclude": rca.responsibility(session, record)
            in {"local", "liechtenstein"},
            "case_priority": case_updates.priority(session, record),
            "role_findings": {
                key: case_updates.label(event.data.get("finding") if event else None)
                for key in ("end_user", "mah")
                for event in [case_updates.latest_finding(session, record, key)]
            },
            "update_history": session.scalars(
                select(AlertDeskCaseUpdate)
                .where(AlertDeskCaseUpdate.exception_id == record.id)
                .order_by(AlertDeskCaseUpdate.id.desc())
                .limit(10)
            ).all(),
            **pilot_context(session, record, view),
        },
    )


@router.get("/exceptions/{identifier}/invitations", include_in_schema=False)
def invitations(
    request: Request,
    identifier: int,
    session: DbSession,
    role: InvitationRole = "end_user",
):
    require_invitation_staff(request)
    return render_invitations(request, session, current(session, identifier), role)


@router.get("/exceptions/{identifier}/invitations/preview", include_in_schema=False)
def live_invitation_preview(
    request: Request,
    identifier: int,
    session: DbSession,
    role: InvitationRole = "end_user",
    report_id: int | None = None,
):
    require_invitation_staff(request)
    record = current(session, identifier)
    if record.source_market == "LI" and role == "mah":
        raise HTTPException(404, "This case is scoped to the End User.")
    if record.error_code not in {"A2", "A3", "A7", "A24"} or (record.error_code == "A24" and role != "end_user"):
        raise HTTPException(404, "No participant template for this alert.")
    view = exception_queries.enriched(session, [record])[0]
    organisation, location = view["organisation"], view["location"]
    prechecks = collect(session, record)
    published = pilot.publication(
        session,
        record,
        organisation,
        location,
        view,
        prechecks,
        role=role,
        share_report=report_id is not None and report_id == prechecks["report_id"],
    )
    closed = rca.is_closed(view["review"], record)
    batch_count = 0
    investigation = pilot.investigation_for(record, organisation, location, role)
    if not closed and investigation:
        cohort = access.export_cohort(session, record) if record.error_code == "A7" else None
        crm = (
            session.get(access.DIRECTORIES[role], cohort.end_user_id)
            if cohort and role == "end_user"
            else audience.organisation_for(
                session, record, organisation.id if organisation else None, role
            )
        )
        if crm and not crm.archived_at:
            batch = access.batch_targets(session, role, crm, record)
            batch_count = len(batch) + 1 if batch else 0
    published.update(
        batch_count=batch_count,
        progress={"closed": closed},
        code=record.error_code,
        label=ERRORS[record.error_code][0],
        investigation=investigation,
    )
    response = render_case(
        request, published, preview=True, assets="/exceptions/invitation-assets"
    )
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'",
        }
    )
    return response


@router.get("/exceptions/invitation-assets/{name}", include_in_schema=False)
@router.get("/exceptions/invitation-assets/design/{name}", include_in_schema=False)
def live_invitation_asset(request: Request, name: str):
    require_invitation_staff(request)
    if name in DESIGN_STYLES:
        return FileResponse(DESIGN_ASSETS / name, media_type="text/css")
    if name in {"case.js", "case.css"}:
        return FileResponse(ASSETS / name)
    raise HTTPException(404)


def access_directory(session):
    history = {
        (item.role, item.crm_organisation_id, item.contact_id): item
        for item in session.scalars(select(AlertDeskAccess))
    }
    assignments = [
        (role, org, contact_id)
        for role, model in access.DIRECTORIES.items()
        for org in session.scalars(select(model).where(model.archived_at.is_(None)))
        for contact_id in set((org.profile or {}).get("alert_contact_ids", []))
    ]
    contact_ids = {contact_id for _, _, contact_id in assignments}
    contacts = {
        contact.id: contact
        for contact in session.scalars(
            select(CRMContact).where(
                CRMContact.id.in_(contact_ids), CRMContact.archived_at.is_(None)
            )
        )
    }
    rows = []
    for role, organisation, contact_id in assignments:
        if (contact := contacts.get(contact_id)) is None:
            continue
        grant = history.get((role, organisation.id, contact.id))
        email = (contact.profile or {}).get("email")
        active = (
            grant
            and grant.contact_version == contact.version
            and grant.scope_key == access.scope_key(role, organisation)
            and not grant.revoked_at
        )
        if not grant:
            status = "Not invited"
        elif not active:
            status = "Access revoked" if grant.revoked_at else "CRM assignment changed"
        elif grant.accepted_at:
            status = (
                "Access confirmed"
                if grant.session_expires_at and grant.session_expires_at > pilot.now()
                else "Session expired"
            )
        elif not grant.sent_at:
            status = "Delivery unconfirmed"
        else:
            status = (
                "Sent"
                if grant.invite_expires_at > pilot.now()
                else "Invitation expired"
            )
        rows.append(
            {
                "key": f"{role}:{organisation.id}:{contact.id}:{contact.version}",
                "role": role,
                "organisation": organisation,
                "contact": contact,
                "email": email,
                "grant": grant,
                "status": status,
                "sendable": audience.deliverable(email)
                and status
                in {
                    "Not invited",
                    "Access revoked",
                    "CRM assignment changed",
                    "Session expired",
                    "Invitation expired",
                },
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["role"],
            row["organisation"].name.casefold(),
            row["contact"].display_name.casefold(),
        ),
    )


def invitation_directory_scope(request):
    role = request.query_params.get("role")
    organisation_id = request.query_params.get("organisation_id")
    case_id = request.query_params.get("case_id")
    if role is None and organisation_id is None and case_id is None:
        return None
    try:
        scope = (role, int(organisation_id), int(case_id))
    except (TypeError, ValueError):
        raise HTTPException(422, "Choose a valid invitation scope.") from None
    if role not in rca.ROLES or min(scope[1:]) < 1:
        raise HTTPException(422, "Choose a valid invitation scope.")
    return scope


def invitation_rows(session, scope):
    rows = access_directory(session)
    if scope:
        role, organisation_id, _ = scope
        rows = [
            row for row in rows
            if row["role"] == role and row["organisation"].id == organisation_id
        ]
    return rows


def render_access_directory(request, session, notice=None):
    scope = invitation_directory_scope(request)
    rows = invitation_rows(session, scope)
    send_url = "/workflows/alert-desk/send"
    case_url = None
    if scope:
        role, organisation_id, case_id = scope
        send_url += f"?role={role}&organisation_id={organisation_id}&case_id={case_id}"
        case_url = f"/exceptions/{case_id}/analysis"
    return templates.TemplateResponse(
        request=request,
        name="alert_desk_access.html",
        headers={"Cache-Control": "no-store"},
        context={
            "title": "Alert Desk invitations",
            "active": "workflows",
            "rows": rows,
            "send_url": send_url,
            "case_url": case_url,
            "notice": notice,
            "test_mailbox_url": "/workflows/alert-desk/mailbox"
            if get_settings().environment == "test" else "http://localhost:18025/",
            "sent_count": sum(
                bool(row["grant"] and row["grant"].sent_at) for row in rows
            ),
            "confirmed_count": sum(row["status"] == "Access confirmed" for row in rows),
        },
    )


@router.get("/workflows/alert-desk", include_in_schema=False)
def access_invitations(request: Request, session: DbSession):
    require_invitation_staff(request)
    return render_access_directory(request, session)


@router.get("/workflows/alert-desk/mailbox", include_in_schema=False)
def test_mailbox(request: Request):
    from app.portal.test_mailbox import page

    return page(request)


@router.get("/workflows/alert-desk/mailbox/{identifier}", include_in_schema=False)
def test_mail_message(request: Request, identifier: str):
    from app.portal.test_mailbox import page

    return page(request, identifier)


@router.post("/workflows/alert-desk/send", include_in_schema=False)
async def send_access_invitations(request: Request, session: DbSession):
    actor, data = await pilot_form(request)
    selected = set(filter(None, data.get("selected", "").split(",")))
    if not selected:
        return render_access_directory(
            request, session, "Select at least one alert contact."
        )
    rows = {row["key"]: row for row in invitation_rows(session, invitation_directory_scope(request))}
    if not selected <= rows.keys():
        raise HTTPException(
            409, "The selected CRM assignments changed. Reload the directory."
        )
    contact_ids = sorted({rows[key]["contact"].id for key in selected})
    locked = {
        row.id: row
        for row in session.scalars(
            select(CRMContact)
            .where(CRMContact.id.in_(contact_ids))
            .order_by(CRMContact.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    pending = []
    for key in sorted(selected):
        row = rows[key]
        contact = locked.get(row["contact"].id)
        if (
            not row["sendable"]
            or not contact
            or contact.archived_at
            or not key.endswith(f":{contact.version}")
        ):
            continue
        role = row["role"]
        organisation = session.get(
            access.DIRECTORIES[role],
            row["organisation"].id,
            with_for_update=True,
            populate_existing=True,
        )
        if (
            not organisation
            or organisation.archived_at
            or contact.id
            not in (organisation.profile or {}).get("alert_contact_ids", [])
        ):
            continue
        issued = access.issue(session, role, organisation, contact, actor.id)
        if issued:
            grant, token = issued
            pending.append((grant.id, row["email"], token))
    session.commit()

    sent = 0
    for identifier, email, token in pending:
        try:
            await run_in_threadpool(pilot_mail.send_access, email, token)
        except (OSError, ValueError):
            continue
        grant = session.get(
            AlertDeskAccess, identifier, with_for_update=True, populate_existing=True
        )
        if grant.invite_hash == pilot.digest(token) and not grant.revoked_at:
            grant.sent_at = pilot.now()
        session.commit()
        sent += 1
    return render_access_directory(
        request,
        session,
        f"{sent} of {len(selected)} selected invitations accepted by the local test mailbox.",
    )


@router.post("/workflows/alert-desk/{identifier}/revoke", include_in_schema=False)
async def revoke_access_invitation(
    request: Request, identifier: int, session: DbSession
):
    await pilot_form(request)
    grant = session.get(AlertDeskAccess, identifier, with_for_update=True)
    if not grant:
        raise HTTPException(404, "Invitation not found.")
    grant.revoked_at = pilot.now()
    grant.invite_hash = grant.session_hash = grant.challenge_hash = grant.code_hash = (
        None
    )
    session.commit()
    return RedirectResponse("/workflows/alert-desk", status_code=303)


@router.post(
    "/exceptions/{identifier}/invitations/case-update", include_in_schema=False
)
async def publish_case_update(request: Request, identifier: int, session: DbSession):
    actor, form = await pilot_form(request)
    current(session, identifier)
    record = session.get(
        NMVSException, identifier, with_for_update=True, populate_existing=True
    )
    if record.payload_hash != form.get("basis"):
        raise HTTPException(409, "The alert changed. Review the case again.")
    previous = case_updates.latest_update(session, record, lock=True)
    previous_id = str(previous.id) if previous else ""
    if form.get("update_version") != previous_id:
        raise HTTPException(409, "The SMVS update changed. Review the case again.")
    pack = form.get("pack_instruction")
    note = form.get("note", "").strip()
    follow_up = form.get("follow_up") == "yes"
    concluded = form.get("concluded") == "yes"
    if concluded and rca.responsibility(session, record) not in {
        "local",
        "liechtenstein",
    }:
        raise HTTPException(
            409, "Confirm SMVS responsibility before concluding this case."
        )
    if (
        pack not in case_updates.PACK_LABELS
        or not note
        or len(note) > 1500
        or (pack == "suspected" and record.error_code not in {"A2", "A3"})
        or (pack == "none" and previous and previous.pack_instruction != "none")
        or (follow_up and concluded)
    ):
        raise HTTPException(
            422, "Check the pack instruction, case status and participant message."
        )
    changed_instruction = pack != (
        previous.pack_instruction if previous else "none"
    ) or (
        pack != "none" and previous and previous.source_version != record.payload_hash
    )
    end_user_event = case_updates.latest_finding(session, record, "end_user", lock=True)
    baseline = end_user_event.id if end_user_event else None
    if previous and (
        previous.source_version,
        previous.pack_instruction,
        previous.follow_up,
        previous.concluded,
        previous.note,
        previous.end_user_event_id,
    ) == (record.payload_hash, pack, follow_up, concluded, note, baseline):
        return RedirectResponse(
            f"/exceptions/{identifier}/invitations#smvs-update", status_code=303
        )
    notify = (
        changed_instruction
        or (concluded and not (previous and previous.concluded))
        or follow_up
    )
    addresses = case_updates.end_user_recipients(session, record) if notify else []
    response_request = None
    if follow_up and addresses:
        view = exception_queries.enriched(session, [record])[0]
        crm, recipients, issue = responses.recipient_scope(
            session, record, "end_user", view
        )
        if not issue:
            scoped_baseline = case_updates.latest_finding(
                session, record, "end_user", crm.id
            )
            response_request = (
                crm.id,
                {email.casefold() for email in recipients},
                scoped_baseline.id if scoped_baseline else 0,
                responses.settings_days(session),
            )
    update = AlertDeskCaseUpdate(
        exception_id=record.id,
        source_version=record.payload_hash,
        actor_id=actor.id,
        end_user_event_id=baseline,
        created_at=pilot.now(),
        pack_instruction=pack,
        note=note,
        follow_up=follow_up,
        concluded=concluded,
        notification="Pending"
        if addresses
        else "No eligible recipients"
        if notify
        else "Not required",
    )
    session.add(update)
    session.commit()
    if addresses:
        sent = 0
        accepted = set()
        for email in addresses:
            try:
                await run_in_threadpool(
                    pilot_mail.send_case_update,
                    email,
                    record.unique_alert_id,
                    record.id,
                )
            except (OSError, ValueError):
                continue
            sent += 1
            accepted.add(email.casefold())
        update.notification = f"{sent} of {len(addresses)} accepted by test mailbox"
        if response_request and accepted & response_request[1]:
            current_record = session.get(
                NMVSException, identifier, with_for_update=True, populate_existing=True
            )
            if current_record.payload_hash == form[
                "basis"
            ] and not rca.resolved_for_source(
                session.get(ExceptionReview, identifier), current_record
            ):
                previous_request = responses.case_requests(session, current_record).get(
                    "end_user"
                )
                if not previous_request or previous_request[1]:
                    crm_id, _, after_event_id, days = response_request
                    session.add(
                        AlertDeskResponseRequest(
                            exception_id=identifier,
                            role="end_user",
                            crm_organisation_id=crm_id,
                            source_version=current_record.payload_hash,
                            after_event_id=after_event_id,
                            actor_id=actor.id,
                            requested_at=pilot.now(),
                            due_on=responses.deadline(responses.today(), days),
                        )
                    )
        session.commit()
    return RedirectResponse(
        f"/exceptions/{identifier}/invitations#smvs-update", status_code=303
    )


@router.post(
    "/exceptions/{identifier}/analysis/request-response", include_in_schema=False
)
async def request_alert_response(request: Request, identifier: int, session: DbSession):
    actor, form = await pilot_form(request)
    role = form.get("role")
    if role not in rca.ROLES:
        raise HTTPException(422, "Choose a participant.")
    record = session.get(NMVSException, identifier, with_for_update=True)
    if not record or record.source_namespace != exception_queries.namespace(session):
        raise HTTPException(404, "Exception not found.")
    if record.payload_hash != form.get("basis") or rca.resolved_for_source(
        session.get(ExceptionReview, identifier), record
    ):
        raise HTTPException(
            409, "Review the current open case before requesting findings."
        )
    previous = responses.case_requests(session, record).get(role)
    if previous and not previous[1]:
        raise HTTPException(409, "A response from this participant is already pending.")
    view = exception_queries.enriched(session, [record])[0]
    crm, recipients, issue = responses.recipient_scope(session, record, role, view)
    if issue:
        raise HTTPException(409, issue)
    baseline = case_updates.latest_finding(session, record, role, crm.id)
    due_on = responses.deadline(responses.today(), responses.settings_days(session))
    requested_at = pilot.now()
    sent = 0
    for email in recipients:
        try:
            await run_in_threadpool(
                pilot_mail.send_response_request,
                email,
                record.unique_alert_id,
                record.id,
                due_on,
            )
        except (OSError, ValueError):
            continue
        sent += 1
    if not sent:
        raise HTTPException(
            503, "The test mailbox did not accept the request. No deadline was started."
        )
    session.add(
        AlertDeskResponseRequest(
            exception_id=identifier,
            role=role,
            crm_organisation_id=crm.id,
            source_version=record.payload_hash,
            after_event_id=baseline.id if baseline else 0,
            actor_id=actor.id,
            requested_at=requested_at,
            due_on=due_on,
        )
    )
    session.commit()
    notice = (
        "response_requested"
        if sent == len(recipients)
        else "response_partially_requested"
    )
    return RedirectResponse(
        f"/exceptions/{identifier}/analysis?notice={notice}", status_code=303
    )


@router.post("/exceptions/response-reminders", include_in_schema=False)
async def alert_response_reminders(
    request: Request,
    session: DbSession,
    response_party: Literal["", "end_user", "mah"] = "",
):
    _, form = await pilot_form(request)
    identifiers = sorted(
        {int(key[7:]) for key in form if re.fullmatch(r"target_[0-9]{1,10}", key)}
    )
    if not identifiers or len(identifiers) > 50:
        raise HTTPException(422, "Select up to 50 cases to review.")
    confirming = "confirm" in form
    query = (
        select(NMVSException)
        .where(NMVSException.id.in_(identifiers))
        .order_by(NMVSException.id)
    )
    if confirming:
        query = query.with_for_update()
    records = session.scalars(query).all()
    namespace = exception_queries.namespace(session)
    if len(records) != len(identifiers) or any(
        record.source_namespace != namespace for record in records
    ):
        raise HTTPException(404, "A selected case is unavailable.")
    groups = defaultdict(list)
    addresses = {}
    excluded = []
    today = responses.today()
    for view in exception_queries.enriched(session, records):
        record = view["record"]
        if rca.resolved_for_source(view["review"], record):
            continue
        for role, (item, received) in responses.case_requests(session, record).items():
            if (
                (response_party and role != response_party)
                or received
                or item.due_on >= today
            ):
                continue
            crm, recipients, issue = responses.recipient_scope(
                session, record, role, view
            )
            if issue or crm.id != item.crm_organisation_id or item.reminded_on == today:
                reason = issue or (
                    "CRM assignment changed"
                    if crm.id != item.crm_organisation_id
                    else "Already reminded today"
                )
                excluded.append((record.unique_alert_id, rca.ROLES[role], reason))
                continue
            for email in recipients:
                groups[addresses.setdefault(email.casefold(), email)].append(
                    (item, record)
                )
    revision = sha256(
        repr(
            [
                (email, [item.id for item, _ in items])
                for email, items in sorted(groups.items())
            ]
        ).encode()
    ).hexdigest()
    back = "/exceptions?response_status=overdue"
    if response_party:
        back += f"&response_party={response_party}"
    context = {
        "title": "Review overdue reminders",
        "active": "exceptions",
        "back": back,
        "groups": dict(sorted(groups.items())),
        "excluded": excluded,
        "identifiers": identifiers,
        "revision": revision,
        "roles": rca.ROLES,
    }
    if confirming:
        if form["confirm"] != revision or not groups:
            raise HTTPException(
                409, "The reminder selection changed. Review the cases again."
            )
        sent = 0
        for email, items in groups.items():
            cases = [
                (record.unique_alert_id, rca.ROLES[item.role], item.due_on, record.id)
                for item, record in items
            ]
            try:
                await run_in_threadpool(pilot_mail.send_response_reminder, email, cases)
            except (OSError, ValueError):
                continue
            sent += 1
            for item, _ in items:
                item.reminded_on = today
        session.commit()
        context["sent"] = sent
    return templates.TemplateResponse(
        request=request,
        name="alert_desk_reminders.html",
        context=context,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/workflows/alert-desk/review", include_in_schema=False)
def alert_desk_priority_review(
    request: Request, session: DbSession, before: int | None = None
):
    require_invitation_staff(request)
    query = case_updates.priority_cases(exception_queries.namespace(session))
    if before:
        query = query.where(NMVSException.id < before)
    rows = session.scalars(query.order_by(NMVSException.id.desc()).limit(51)).all()
    return templates.TemplateResponse(
        request=request,
        name="alert_desk_review.html",
        context={
            "title": "Alert Desk priority review",
            "active": "workflows",
            "rows": rows[:50],
            "next": rows[49].id if len(rows) > 50 else None,
        },
    )
