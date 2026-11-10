"""Persist unambiguous imported MAH contacts without replacing manual choices."""

from collections import Counter

from sqlalchemy import select

from app.core.db.models import StagingRow
from app.domain.crm.contact_assignments import has_spoc_assignment
from app.domain.crm.end_users import contact_reference_index, resolve_end_user_contacts
from app.domain.models import CRMMah
from app.integration.artifacts.storage import utcnow

ROLE_FIELDS = {"SPOC": "spoc_ids", "Alert contacts": "alert_contact_ids"}


def proposed_assignments(source, profile, index):
    profile = profile or {}
    missing = {
        field
        for field in ROLE_FIELDS.values()
        if field not in profile
        and (field != "spoc_ids" or not has_spoc_assignment(profile))
    }
    assignments, pending = resolve_end_user_contacts(source, index)
    pending = [
        item for item in pending if ROLE_FIELDS[item.split(" · ", 1)[0]] in missing
    ]
    blocked = {ROLE_FIELDS[item.split(" · ", 1)[0]] for item in pending}
    # Do not silently import only part of a role when another reference is ambiguous.
    additions = {
        field: ids
        for field, ids in assignments.items()
        if field in missing and field not in blocked
    }
    return additions, pending


def plan_mah_contacts(session, *, lock=False):
    index = contact_reference_index(session)
    query = (
        select(CRMMah, StagingRow.raw_row_json)
        .join(StagingRow, CRMMah.source_row_id == StagingRow.id)
        .where(CRMMah.archived_at.is_(None))
        .order_by(CRMMah.id)
    )
    if lock:
        query = query.with_for_update()
    return [
        (mah, *proposed_assignments(source, mah.profile, index))
        for mah, source in session.execute(query)
    ]


def seed_mah_contacts(session):
    changed = Counter()
    for mah, additions, _ in plan_mah_contacts(session, lock=True):
        if additions:
            mah.profile = (mah.profile or {}) | additions
            mah.updated_at = utcnow()
            changed.update(additions.keys())
    return changed
