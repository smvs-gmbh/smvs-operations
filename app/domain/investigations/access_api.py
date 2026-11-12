"""Private Alert Desk organisation capability endpoints."""

import hmac
import secrets
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, or_, select

from app.alert_desk.schema import Capability, Findings, MailboxCode
from app.domain.investigations import access, case_updates, pilot, pilot_mail
from app.domain.investigations.prechecks import collect
from app.domain.investigations.preview import ERRORS, utc
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskEvent,
    AlertDeskGrant,
    NMVSException,
)
from app.portal.exception_queries import enriched, namespace


def install(app, sessions, secret):
    def capability(request: Request):
        try:
            return Capability(token=request.headers.get("x-case-session", "")).token
        except ValueError:
            raise HTTPException(404, "Alert Desk access unavailable.") from None

    def active(session, token, *, lock=False):
        result = access.lookup(session, AlertDeskAccess.session_hash, token, lock=lock)
        if (
            not result
            or not result[0].session_expires_at
            or result[0].session_expires_at <= pilot.now()
        ):
            raise HTTPException(404, "Alert Desk access unavailable.")
        return result[0], result[1]

    def current_case(session, grant, crm, identifier, *, lock=False):
        query = access.cases(session, grant.role, crm, namespace(session)).where(
            NMVSException.id == identifier
        )
        record = session.scalar(
            query.with_for_update().execution_options(populate_existing=True)
            if lock
            else query
        )
        if not record:
            raise HTTPException(404, "Case unavailable.")
        return record

    def existing_case_grant(session, grant, record):
        rows = session.scalars(
            select(AlertDeskGrant).where(
                AlertDeskGrant.exception_id == record.id,
                AlertDeskGrant.source_version == record.payload_hash,
            )
        )
        return next(
            (
                row
                for row in rows
                if row.publication.get("organisation_access") == grant.id
            ),
            None,
        )

    @app.post("/access/challenge")
    def challenge(body: Capability):
        with sessions() as session, session.begin():
            result = access.lookup(
                session, AlertDeskAccess.invite_hash, body.token, lock=True
            )
            now = pilot.now()
            if not result or result[0].invite_expires_at <= now:
                raise HTTPException(404, "Invitation unavailable.")
            grant, _, email = result
            if grant.code_expires_at and grant.code_expires_at > now:
                raise HTTPException(
                    409,
                    "A code is already active. Use it in the original tab or wait ten minutes.",
                )
            token = secrets.token_urlsafe(32)
            code = f"{secrets.randbelow(1_000_000):06d}"
            grant.challenge_hash = pilot.digest(token)
            grant.code_hash = access.code_hash(secret, token, code)
            grant.code_expires_at = now + timedelta(minutes=10)
            grant.attempts_left = 5
            try:
                pilot_mail.send_code(email, code)
            except (OSError, ValueError):
                raise HTTPException(503, "The code could not be sent.") from None
        return {"token": token}

    @app.post("/access/verify")
    def verify(body: MailboxCode):
        token = None
        with sessions() as session, session.begin():
            result = access.lookup(
                session, AlertDeskAccess.challenge_hash, body.token, lock=True
            )
            now = pilot.now()
            if result:
                grant = result[0]
                if (
                    grant.invite_expires_at > now
                    and grant.code_expires_at
                    and grant.code_expires_at > now
                    and grant.attempts_left > 0
                ):
                    grant.attempts_left -= 1
                    if hmac.compare_digest(
                        grant.code_hash or "",
                        access.code_hash(secret, body.token, body.code),
                    ):
                        token = secrets.token_urlsafe(32)
                        grant.invite_hash = grant.challenge_hash = grant.code_hash = (
                            None
                        )
                        grant.code_expires_at = None
                        grant.session_hash = pilot.digest(token)
                        grant.session_expires_at = now + timedelta(hours=8)
                        grant.accepted_at = now
        if not token:
            raise HTTPException(422, "Invalid or expired verification code.")
        return {"token": token}

    @app.get("/access/alerts")
    def list_alerts(
        token: Annotated[str, Depends(capability)],
        before: int | None = None,
        view: Literal["my_cases", "completed", "on_hold", "all"] = "my_cases",
        finding: Literal[
            "all", "new", "investigating", "not_my_side", "on_my_side"
        ] = "all",
        q: str = "",
    ):
        with sessions() as session:
            grant, crm = active(session, token)
            query, own_finding, held, open_case = case_updates.with_status(
                access.cases(session, grant.role, crm, namespace(session)),
                grant.role,
                crm.id,
            )
            hold_count = session.scalar(
                query.where(held).with_only_columns(
                    func.count(), maintain_column_froms=True
                )
            )
            if q.strip():
                term = q.strip()[:100]
                query = query.where(
                    or_(
                        NMVSException.unique_alert_id.icontains(term, autoescape=True),
                        NMVSException.provided_batch.icontains(term, autoescape=True),
                        NMVSException.gtin14.icontains(term, autoescape=True),
                        NMVSException.error_code.icontains(term, autoescape=True),
                    )
                )
            if view == "my_cases":
                query = query.where(open_case)
            elif view == "completed":
                query = query.where(~open_case)
            elif view == "on_hold":
                query = query.where(held)
            if finding == "new":
                query = query.where(own_finding.is_(None))
            elif finding == "on_my_side":
                query = query.where(own_finding.in_(case_updates.OWN_FINDINGS))
            elif finding != "all":
                query = query.where(own_finding == finding)
            if before:
                query = query.where(NMVSException.id < before)
            records = session.execute(
                query.order_by(NMVSException.id.desc()).limit(access.PAGE_SIZE + 1)
            ).all()
            rows = [
                {
                    "id": record.id,
                    "alert": record.unique_alert_id,
                    "at": utc(record.alert_at),
                    "type": record.error_code,
                    "label": ERRORS.get(record.error_code, ("Reported alert",))[0],
                    "finding": case_updates.label(
                        event.data.get("finding") if event else None
                    ),
                    "follow_up": bool(follow_up),
                    "pack_label": case_updates.PACK_LABELS[
                        "suspected"
                        if update and update.pack_instruction == "suspected"
                        else "hold"
                    ]
                    if on_hold
                    else "",
                }
                for record, event, update, on_hold, follow_up in records[
                    : access.PAGE_SIZE
                ]
            ]
            return {
                "organisation": crm.name,
                "role": grant.role,
                "hold_count": hold_count,
                "rows": rows,
                "next": rows[-1]["id"] if len(records) > access.PAGE_SIZE else None,
            }

    @app.get("/access/alerts/{identifier}")
    def read_case(identifier: int, token: Annotated[str, Depends(capability)]):
        with sessions() as session:
            grant, crm = active(session, token)
            record = current_case(session, grant, crm, identifier)
            view = enriched(session, [record])[0]
            case = pilot.publication(
                session,
                record,
                view["organisation"],
                view["location"],
                view,
                collect(session, record),
                role=grant.role,
            )
            latest = case_updates.latest_finding(session, record, grant.role, crm.id)
            progress = case_updates.public_progress(
                session, record, grant.role, crm.id, latest
            )
            batch = access.batch_targets(session, grant.role, crm, record)
            return {
                **case,
                "batch_count": len(batch) + 1 if batch else 0,
                "batch_revision": access.batch_revision(batch) if batch else None,
                "organisation": crm.name
                if grant.role == "end_user"
                else case["organisation"],
                "publication": record.id,
                "basis": record.payload_hash,
                "latest": latest.data if latest else None,
                "progress": progress,
                "code": record.error_code,
                "label": ERRORS.get(record.error_code, ("Reported alert",))[0],
                "investigation": pilot.investigation_for(
                    record, view["organisation"], view["location"], grant.role
                ),
            }

    @app.post("/access/alerts/{identifier}/findings")
    def submit_case(
        identifier: int, body: Findings, token: Annotated[str, Depends(capability)]
    ):
        with sessions() as session, session.begin():
            grant, crm = active(session, token)
            session.get(
                access.DIRECTORIES[grant.role],
                crm.id,
                with_for_update=True,
                populate_existing=True,
            )
            grant, crm = active(session, token, lock=True)
            if body.batch_revision:
                anchor = current_case(session, grant, crm, identifier)
                access.export_cohort(
                    session,
                    anchor,
                    end_user_id=crm.id if grant.role == "end_user" else None,
                    lock=True,
                )
            record = current_case(session, grant, crm, identifier, lock=True)
            view = enriched(session, [record])[0]
            org, location = view["organisation"], view["location"]
            if body.publication != identifier or body.basis != record.payload_hash:
                raise HTTPException(409, "Reload the case before submitting.")
            if not pilot.investigation_for(
                record, org, location, grant.role
            ) or not body.matches_audience(grant.role, record.error_code):
                raise HTTPException(422, "Check your answers and try again.")
            stored = existing_case_grant(session, grant, record)
            key = str(body.submission_key)
            data = body.model_dump(
                mode="json",
                exclude={"submission_key", "publication", "basis", "batch_revision"},
            )
            if body.batch_revision:
                data["batch_revision"] = body.batch_revision
            previous = (
                session.scalar(
                    select(AlertDeskEvent).where(
                        AlertDeskEvent.grant_id == stored.id,
                        AlertDeskEvent.submission_key == key,
                    )
                )
                if stored
                else None
            )
            if previous:
                count = previous.data.get("batch_count")
                if {
                    k: v for k, v in previous.data.items() if k != "batch_count"
                } != data:
                    raise HTTPException(409, "Reload the case before submitting.")
                return {"received": True, **({"batch_count": count} if count else {})}

            batch = []
            if body.batch_revision:
                batch = access.batch_targets(
                    session, grant.role, crm, record, lock=True
                )
                if not batch or access.batch_revision(batch) != body.batch_revision:
                    raise HTTPException(
                        409,
                        "The matching alerts changed. Reload the case and review the selection.",
                    )
                data["batch_count"] = len(batch) + 1

            def store_findings(target, case_grant, event_data):
                if not case_grant:
                    case_grant = AlertDeskGrant(
                        exception_id=target.id,
                        organisation_id=org.id if org else None,
                        location_id=location.id if location else None,
                        source_version=target.payload_hash,
                        publication={
                            "organisation_access": grant.id,
                            "audience": grant.role,
                            "recipient": {"contact": grant.contact_id},
                        },
                        expires_at=pilot.now(),
                    )
                    session.add(case_grant)
                    session.flush()
                pilot.append_event(
                    session, case_grant, "Findings submitted", data=event_data, key=key
                )

            store_findings(record, stored, data)
            if batch:
                existing_grants = {
                    row.exception_id: row
                    for row in session.scalars(
                        select(AlertDeskGrant)
                        .join(
                            NMVSException,
                            NMVSException.id == AlertDeskGrant.exception_id,
                        )
                        .where(
                            AlertDeskGrant.exception_id.in_(
                                [target.id for target in batch]
                            ),
                            AlertDeskGrant.source_version == NMVSException.payload_hash,
                            AlertDeskGrant.publication[
                                "organisation_access"
                            ].as_integer()
                            == grant.id,
                        )
                        .with_for_update()
                    )
                }
                copied = {
                    k: v
                    for k, v in data.items()
                    if k not in {"batch_count", "batch_revision"}
                }
                for target in batch:
                    store_findings(
                        target,
                        existing_grants.get(target.id),
                        {**copied, "batch_source": record.id},
                    )
        return {"received": True, **({"batch_count": len(batch) + 1} if batch else {})}
