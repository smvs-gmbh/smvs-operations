"""Resolve invitation recipients from the alert contact assignments in CRM."""

import hashlib
import json
from email.errors import HeaderParseError
from email.headerregistry import Address

from sqlalchemy import select

from app.domain.crm.declaration_workflow import usable_email
from app.domain.models import (
    CRMContact,
    CRMEndUser,
    CRMMah,
    CurrentPublication,
    SAIHolder,
    SAIPackage,
    SAIPreparation,
)


def organisation_for(session, record, organisation_id, audience):
    if audience == "end_user":
        if organisation_id is None:
            return None
        return session.scalar(
            select(CRMEndUser).where(
                CRMEndUser.organisation_id == organisation_id,
                CRMEndUser.archived_at.is_(None),
            )
        )
    publication = session.get(CurrentPublication, "product-batch")
    if (
        not publication
        or publication.source_namespace != record.source_namespace
        or not record.gtin14
    ):
        return None
    holders = session.scalars(
        select(SAIHolder)
        .select_from(SAIPackage)
        .join(SAIPreparation, SAIPackage.preparation_id == SAIPreparation.id)
        .join(SAIHolder, SAIPreparation.holder_id == SAIHolder.id)
        .where(
            SAIPackage.gtin14 == record.gtin14,
            SAIPackage.is_observed == 1,
            SAIPackage.last_mapping_run_id == publication.mapping_run_id,
            SAIHolder.is_observed == 1,
        )
        .limit(2)
    ).all()
    if len(holders) != 1 or not holders[0].gln:
        return None
    matches = session.scalars(
        select(CRMMah)
        .where(CRMMah.gln == holders[0].gln, CRMMah.archived_at.is_(None))
        .limit(2)
    ).all()
    return matches[0] if len(matches) == 1 else None


def deliverable(email):
    if not isinstance(email, str) or not usable_email(email):
        return False
    try:
        return Address(addr_spec=email).addr_spec == email
    except (HeaderParseError, ValueError):
        return False


def recipients(session, organisation):
    identifiers = (
        (organisation.profile or {}).get("alert_contact_ids", [])
        if organisation
        else []
    )
    if not identifiers:
        return []
    contacts = session.scalars(
        select(CRMContact)
        .where(CRMContact.id.in_(identifiers), CRMContact.archived_at.is_(None))
        .order_by(CRMContact.id)
    ).all()
    seen = set()
    result = []
    for contact in contacts:
        email = (contact.profile or {}).get("email")
        if deliverable(email) and email.casefold() not in seen:
            seen.add(email.casefold())
            result.append((contact, email))
    return result


def revision(organisation, contacts):
    values = [
        organisation.id if organisation else None,
        [(c.id, c.version, email) for c, email in contacts],
    ]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()
