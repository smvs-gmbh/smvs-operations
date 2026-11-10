"""Explicit administrator erasure, retaining only a minimal deletion audit."""

from sqlalchemy import delete, select

from app.domain.crm.contact_assignments import spoc_ids
from app.domain.crm.contact_deletions import contact_source_hash
from app.domain.models import (
    Base,
    CRMContact,
    CRMDeletionEvent,
    CRMEndUser,
    CRMMah,
    EndUserRegistration,
    RegistrationEvent,
    RegistrationReceipt,
)
from app.integration.artifacts.storage import utcnow


def check_references(
    session,
    row,
    excluded_registration=None,
    excluded_end_user=None,
    *,
    detach_contact=False,
):
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if any(fk.column.table is row.__table__ for fk in column.foreign_keys):
                query = select(column).where(column == row.id)
                if table is EndUserRegistration.__table__ and excluded_registration:
                    query = query.where(table.c.id != excluded_registration)
                if session.execute(query.limit(1)).first():
                    raise ValueError(
                        "Remove linked records or delete the registration first."
                    )
    if isinstance(row, CRMContact) and not detach_contact:
        for model in (CRMMah, CRMEndUser):
            for owner in session.scalars(select(model).with_for_update()):
                if model is CRMEndUser and owner.id == excluded_end_user:
                    continue
                profile = owner.profile or {}
                if row.id in set(spoc_ids(profile)) | set(
                    profile.get("alert_contact_ids", [])
                ):
                    raise ValueError(
                        "This contact is assigned to another CRM record. Remove that assignment first."
                    )


def log_deletion(session, row, actor):
    session.add(
        CRMDeletionEvent(
            record_type=row.__tablename__,
            source_identity_hash=contact_source_hash(row.airtable_id)
            if isinstance(row, CRMContact)
            else None,
            record_id=row.id,
            actor_user_id=actor.id,
            occurred_at=utcnow(),
        )
    )


def contact_assignment_owners(session, identifier, *, lock=False):
    owners = []
    for model, directory in ((CRMMah, "mahs"), (CRMEndUser, "end-users")):
        query = select(model).order_by(model.id)
        if lock:
            query = query.with_for_update()
        for owner in session.scalars(query):
            profile = owner.profile or {}
            if identifier in set(spoc_ids(profile)) | set(
                profile.get("alert_contact_ids", [])
            ):
                owners.append((owner, directory))
    return owners


def erase_record(session, row, actor):
    check_references(session, row, detach_contact=isinstance(row, CRMContact))
    if isinstance(row, CRMContact):
        for owner, _ in contact_assignment_owners(session, row.id, lock=True):
            profile = dict(owner.profile or {})
            if row.id in spoc_ids(profile):
                profile["spoc_ids"] = [
                    identifier
                    for identifier in spoc_ids(profile)
                    if identifier != row.id
                ]
                profile.pop("spoc_id", None)
            if row.id in profile.get("alert_contact_ids", []):
                profile["alert_contact_ids"] = [
                    identifier
                    for identifier in profile["alert_contact_ids"]
                    if identifier != row.id
                ]
            owner.profile = profile
            if isinstance(owner, CRMMah):
                owner.updated_at = utcnow()
    log_deletion(session, row, actor)
    session.delete(row)


def erase_registration(session, row, actor, include_crm=False):
    receipt = session.get(RegistrationReceipt, row.intake_id, with_for_update=True)
    if receipt and receipt.mail_status == "sending":
        raise ValueError(
            "A confirmation email is being processed. Wait before deleting this registration."
        )
    records = []
    if include_crm:
        for model, identifier in (
            (CRMEndUser, row.end_user_id),
            (CRMContact, row.contact_id),
        ):
            record = (
                session.get(model, identifier, with_for_update=True)
                if identifier
                else None
            )
            if record:
                check_references(session, record, row.id, row.end_user_id)
                records.append(record)
    if receipt:
        # Keep only a deduplication tombstone: retries must not recreate erased data.
        receipt.payload_ciphertext = receipt.token_ciphertext = receipt.token_digest = (
            None
        )
        receipt.mail_status = "deleted"
        receipt.revision += 1
        receipt.acknowledged_revision = receipt.revision
    session.execute(
        delete(RegistrationEvent).where(RegistrationEvent.registration_id == row.id)
    )
    if not include_crm:
        for model, identifier in (
            (CRMEndUser, row.end_user_id),
            (CRMContact, row.contact_id),
        ):
            record = session.get(model, identifier) if identifier else None
            if record:
                profile = dict(record.profile or {})
                profile.pop("registration_id", None)
                record.profile = profile
    log_deletion(session, row, actor)
    session.delete(row)
    session.flush()
    for record in records:
        log_deletion(session, record, actor)
        session.delete(record)
