"""Non-personal source fingerprints prevent reimport of erased CRM contacts."""

import hashlib

from sqlalchemy import select

from app.domain.models import CRMDeletionEvent


def contact_source_hash(identity):
    return hashlib.sha256(
        ("airtable-contact\0" + identity.strip()).encode()
    ).hexdigest()


def erased_contact_sources(session):
    return set(
        session.scalars(
            select(CRMDeletionEvent.source_identity_hash).where(
                CRMDeletionEvent.record_type == "crm_contacts",
                CRMDeletionEvent.source_identity_hash.is_not(None),
            )
        )
    )
