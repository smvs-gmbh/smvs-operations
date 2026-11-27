"""Per-party response deadlines and recipient scope for Alert Desk requests."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, or_, select

from app.domain.investigations import access, audience, case_updates, pilot, rca
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskEvent,
    AlertDeskSettings,
    ExceptionReview,
    NMVSException,
)
from app.domain.models import (
    AlertDeskResponseRequest as ResponseRequest,
)

NO_INVITATION = "No invitation sent"
INVITATION_INACTIVE = "Invitation expired or no longer valid"
DELIVERY_UNCONFIRMED = "Invitation delivery unconfirmed"
INVITATION_ISSUES = {NO_INVITATION, INVITATION_INACTIVE, DELIVERY_UNCONFIRMED}

DEFAULT_DAYS = 3
ZURICH = ZoneInfo("Europe/Zurich")
STATUS_LABELS = {
    "awaiting": "Awaiting response",
    "overdue": "Overdue",
    "received": "Response received",
    "not_requested": "Not requested",
}


def today():
    return datetime.now(UTC).astimezone(ZURICH).date()


def deadline(start, days):
    while days:
        start += timedelta(days=1)
        if start.weekday() < 5:
            days -= 1
    return start


def settings_days(session):
    settings = session.get(AlertDeskSettings, 1)
    return settings.response_days if settings else DEFAULT_DAYS


def latest_query(role):
    return (
        select(ResponseRequest)
        .where(
            ResponseRequest.exception_id == NMVSException.id,
            ResponseRequest.source_version == NMVSException.payload_hash,
            ResponseRequest.role == role,
        )
        .order_by(ResponseRequest.id.desc())
        .limit(1)
    )


def response_received():
    return (
        case_updates.finding_events(
            ResponseRequest.role, ResponseRequest.crm_organisation_id
        )
        .where(AlertDeskEvent.id > ResponseRequest.after_event_id)
        .correlate(NMVSException, ResponseRequest)
        .exists()
    )


def case_requests(session, record):
    result = {}
    for role in applicable_roles(record):
        row = session.execute(
            latest_query(role)
            .add_columns(response_received())
            .where(NMVSException.id == record.id)
        ).one_or_none()
        if row:
            result[role] = tuple(row)
    return result


def applicable_roles(record):
    return ("end_user",) if record.source_market == "LI" else ("end_user", "mah")


def columns(day, party=""):
    active = or_(
        ExceptionReview.exception_id.is_(None),
        ExceptionReview.status != "resolved",
        ExceptionReview.basis_payload_hash != NMVSException.payload_hash,
    )
    due = {}
    requested = {}
    for role in (party,) if party in rca.ROLES else rca.ROLES:
        allowed = (
            or_(
                NMVSException.source_market.is_(None),
                NMVSException.source_market != "LI",
            )
            if role == "mah"
            else True
        )
        latest = latest_query(role).correlate(NMVSException)
        requested[role] = and_(active, allowed, latest.exists())
        due[role] = case(
            (
                and_(active, allowed),
                latest.with_only_columns(
                    case((~response_received(), ResponseRequest.due_on))
                ).scalar_subquery(),
            )
        )
    end_user = due.get("end_user")
    mah = due.get("mah")
    if end_user is not None and mah is not None:
        waiting = case(
            (and_(end_user.is_not(None), mah.is_not(None)), "End User · MAH"),
            (end_user.is_not(None), "End User"),
            (mah.is_not(None), "MAH"),
        )
        next_due = case((or_(mah.is_(None), end_user <= mah), end_user), else_=mah)
    else:
        next_due = due[party]
        waiting = case((next_due.is_not(None), rca.ROLES[party]))
    status = case(
        (~active, None),
        (next_due < day, STATUS_LABELS["overdue"]),
        (next_due.is_not(None), STATUS_LABELS["awaiting"]),
        (or_(*requested.values()), STATUS_LABELS["received"]),
        else_=STATUS_LABELS["not_requested"],
    )
    return waiting, next_due, status


def recipient_scope(session, record, role, view):
    """Return one matching CRM scope, its invited Alert SPOCs, and an issue label."""
    if (
        role not in applicable_roles(record)
        or rca.responsibility(session, record) == "unconfirmed"
    ):
        return None, [], "Out of scope"
    if not pilot.investigation_for(
        record, view["organisation"], view["location"], role,
        mah_a24_enabled=role == "mah" and record.error_code == "A24",
    ):
        return None, [], "Findings unavailable in Alert Desk"
    if role == "end_user" and record.source_market not in {"CH", "LI"}:
        cohort = access.export_cohort(session, record)
        crm = (
            session.get(access.DIRECTORIES[role], cohort.end_user_id)
            if cohort
            else None
        )
    else:
        organisation = view["organisation"]
        crm = audience.organisation_for(
            session, record, organisation.id if organisation else None, role
        )
    if not crm or crm.archived_at:
        return None, [], "No linked CRM organisation"
    contacts = audience.recipients(session, crm)
    if not contacts:
        return crm, [], "No alert contact"
    if not session.scalar(
        access.cases(session, role, crm, record.source_namespace, include_unrequested=True).where(
            NMVSException.id == record.id
        )
    ):
        return crm, [], "Alert Desk access unavailable"
    grants = {
        grant.contact_id: grant
        for grant in session.scalars(
            select(AlertDeskAccess).where(
                AlertDeskAccess.role == role,
                AlertDeskAccess.crm_organisation_id == crm.id,
            )
        )
    }
    current_grants = {
        contact.id: grant
        for contact, _ in contacts
        if (grant := grants.get(contact.id))
        and grant.contact_version == contact.version
        and grant.scope_key == access.scope_key(role, crm)
        and not grant.revoked_at
    }
    recipients = [
        email
        for contact, email in contacts
        if (grant := current_grants.get(contact.id))
        and grant.sent_at
    ]
    if recipients:
        return crm, recipients, ""
    if any(grant.sent_at for grant in grants.values()):
        return crm, [], INVITATION_INACTIVE
    if current_grants:
        return crm, [], DELIVERY_UNCONFIRMED
    return crm, [], NO_INVITATION
