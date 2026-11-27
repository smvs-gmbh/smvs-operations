"""Shared case progress and pack handling for authorised Alert Desk cases."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from app.domain.investigations import access, rca
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskCaseUpdate,
    AlertDeskEvent,
    AlertDeskGrant,
    ExceptionReview,
    NMVSException,
)

FINDING_LABELS = {
    "new": "New",
    "investigating": "Still investigating",
    "not_my_side": "Root cause not on my side",
    "on_my_side": "Root cause on my side",
}
OWN_FINDINGS = ("on_my_side", "procedural", "technical", "other")
PACK_LABELS = {
    "none": "No pack instruction",
    "hold": "Keep pack on hold",
    "suspected": "Suspected falsification · Keep pack on hold",
    "released": "Quarantine lifted · Follow the case instructions",
}


def finding_events(role, organisation_id=None, *, current=True):
    statement = (
        select(AlertDeskEvent)
        .join(AlertDeskGrant, AlertDeskGrant.id == AlertDeskEvent.grant_id)
        .join(
            AlertDeskAccess,
            AlertDeskGrant.publication["organisation_access"].as_integer()
            == AlertDeskAccess.id,
        )
        .where(
            AlertDeskGrant.exception_id == NMVSException.id,
            AlertDeskAccess.role == role,
            AlertDeskEvent.kind == "Findings submitted",
        )
    )
    if current:
        statement = statement.where(
            AlertDeskGrant.source_version == NMVSException.payload_hash
        )
    if organisation_id is not None:
        statement = statement.where(
            AlertDeskAccess.crm_organisation_id == organisation_id
        )
    return statement.correlate(NMVSException)


def latest_finding(session, record, role, organisation_id=None, *, lock=False):
    statement = (
        finding_events(role, organisation_id)
        .where(NMVSException.id == record.id)
        .order_by(AlertDeskEvent.id.desc())
        .limit(1)
    )
    return session.scalar(statement.with_for_update() if lock else statement)


def participant_hold(role, organisation_id, after_id=None):
    query = finding_events(role, organisation_id, current=False).where(
        AlertDeskEvent.data["pack_on_hold"].as_boolean().is_(True)
    )
    if after_id is not None:
        query = query.where(AlertDeskEvent.id > after_id)
    return query.exists()


def with_status(query, role, organisation_id):
    event = aliased(AlertDeskEvent)
    update = aliased(AlertDeskCaseUpdate)
    event_id = (
        finding_events(role, organisation_id)
        .with_only_columns(AlertDeskEvent.id)
        .order_by(AlertDeskEvent.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    update_id = (
        select(AlertDeskCaseUpdate.id)
        .where(AlertDeskCaseUpdate.exception_id == NMVSException.id)
        .order_by(AlertDeskCaseUpdate.id.desc())
        .limit(1)
        .correlate(NMVSException)
        .scalar_subquery()
    )
    query = query.outerjoin_from(
        NMVSException, event, event.id == event_id
    ).outerjoin_from(NMVSException, update, update.id == update_id)
    finding = event.data["finding"].as_string()
    closed = rca.closed_condition()
    follow_up = and_(
        ~closed,
        role == "end_user",
        update.id.is_not(None),
        update.follow_up.is_(True),
        or_(event.id.is_(None), event.id <= func.coalesce(update.end_user_event_id, 0)),
    )
    held = or_(
        update.pack_instruction.in_(("hold", "suspected")),
        and_(
            update.pack_instruction == "released",
            or_(
                update.source_version != NMVSException.payload_hash,
                participant_hold(
                    role,
                    organisation_id,
                    after_id=func.coalesce(update.end_user_event_id, 0),
                ).correlate(NMVSException, update),
            ),
        ),
        and_(
            or_(update.id.is_(None), update.pack_instruction == "none"),
            participant_hold(role, organisation_id),
        ),
    )
    open_case = and_(
        ~closed, or_(event.id.is_(None), finding == "investigating", follow_up)
    )
    return (
        query.add_columns(event, update, held, follow_up, closed),
        finding,
        held,
        open_case,
    )


def label(finding):
    return FINDING_LABELS.get(
        "on_my_side" if finding in OWN_FINDINGS else finding or "new"
    )


def latest_update(session, record, *, lock=False):
    statement = (
        select(AlertDeskCaseUpdate)
        .where(AlertDeskCaseUpdate.exception_id == record.id)
        .order_by(AlertDeskCaseUpdate.id.desc())
        .limit(1)
    )
    return session.scalar(statement.with_for_update() if lock else statement)


def public_progress(session, record, role, organisation_id, latest):
    update = latest_update(session, record)
    instruction = update.pack_instruction if update else "none"
    stale = bool(update and update.source_version != record.payload_hash)
    closed = rca.is_closed(session.get(ExceptionReview, record.id), record)
    if stale and instruction == "released":
        instruction = "hold"
    if instruction in {"none", "released"}:
        hold = participant_hold(
            role,
            organisation_id,
            after_id=(update.end_user_event_id or 0)
            if instruction == "released"
            else None,
        )
        if session.scalar(select(hold).where(NMVSException.id == record.id)):
            instruction = "hold"
    return {
        "instruction": instruction,
        "pack_label": PACK_LABELS[instruction],
        "follow_up": bool(
            not closed
            and role == "end_user"
            and update
            and update.follow_up
            and (not latest or latest.id <= (update.end_user_event_id or 0))
        ),
        "concluded": bool(update and update.concluded and not stale),
        "closed": closed,
        "note": update.note if update and not stale else "",
        "unresolved": priority(session, record)
        and not (closed or bool(update and update.concluded and not stale)),
    }


def priority(session, record):
    if record.error_code not in {"A2", "A3"} or record.source_market == "LI":
        return False
    events = [latest_finding(session, record, role) for role in ("end_user", "mah")]
    return all(event and event.data.get("finding") == "not_my_side" for event in events)


def end_user_recipients(session, record):
    addresses = {}
    grants = session.scalars(
        select(AlertDeskAccess).where(
            AlertDeskAccess.role == "end_user",
            AlertDeskAccess.sent_at.is_not(None),
            AlertDeskAccess.revoked_at.is_(None),
        )
    )
    for grant in grants:
        member = access.membership(session, grant)
        if not member:
            continue
        crm, address = member
        if session.scalar(
            access.cases(session, grant.role, crm, record.source_namespace).where(
                NMVSException.id == record.id
            )
        ):
            addresses.setdefault(address.casefold(), address)
    return list(addresses.values())


def priority_cases(namespace):
    query = select(NMVSException).where(
        NMVSException.source_namespace == namespace,
        NMVSException.error_code.in_(("A2", "A3")),
        or_(NMVSException.source_market.is_(None), NMVSException.source_market != "LI"),
        ~rca.closed_condition(),
    )
    for role in ("end_user", "mah"):
        result = (
            finding_events(role)
            .with_only_columns(AlertDeskEvent.data["finding"].as_string())
            .order_by(AlertDeskEvent.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        query = query.where(result == "not_my_side")
    concluded = (
        select(AlertDeskCaseUpdate.concluded)
        .where(AlertDeskCaseUpdate.exception_id == NMVSException.id)
        .order_by(AlertDeskCaseUpdate.id.desc())
        .limit(1)
        .correlate(NMVSException)
        .scalar_subquery()
    )
    basis = (
        select(AlertDeskCaseUpdate.source_version)
        .where(AlertDeskCaseUpdate.exception_id == NMVSException.id)
        .order_by(AlertDeskCaseUpdate.id.desc())
        .limit(1)
        .correlate(NMVSException)
        .scalar_subquery()
    )
    return query.where(
        or_(
            concluded.is_(None),
            concluded.is_(False),
            basis != NMVSException.payload_hash,
        )
    )
