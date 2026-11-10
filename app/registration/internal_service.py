"""Atomic internal receipt/CRM transitions in the existing Operations database."""

from sqlalchemy import select

from app.domain.crm import registrations as crm
from app.domain.models import RegistrationReceipt
from app.registration import service
from app.registration.crypto import decrypt


def sync_receipt(session, receipt, key):
    if receipt.mail_status == "deleted":
        return None
    session.flush()
    data = {
        "id": receipt.id,
        "revision": receipt.revision,
        "mail_status": receipt.mail_status,
        "submitted_at": receipt.submitted_at.isoformat() + "Z",
        "confirmed_at": receipt.confirmed_at.isoformat() + "Z"
        if receipt.confirmed_at
        else None,
        "expires_at": receipt.expires_at.isoformat() + "Z",
        "values": decrypt(key, receipt.payload_ciphertext)
        if receipt.payload_ciphertext
        else None,
    }
    row = crm.import_intake(session, data, key)
    service.acknowledge(
        session, receipt.id, receipt.revision, model=RegistrationReceipt
    )
    return row


def synchronise_pending(session, key):
    service.purge(session, model=RegistrationReceipt)
    crm.purge_expired(session)
    session.flush()
    receipts = list(
        session.scalars(
            select(RegistrationReceipt)
            .where(
                RegistrationReceipt.revision > RegistrationReceipt.acknowledged_revision
            )
            .order_by(RegistrationReceipt.received_at, RegistrationReceipt.id)
            .limit(100)
            .with_for_update()
        )
    )
    for receipt in receipts:
        sync_receipt(session, receipt, key)
    return len(receipts)


def receive(session, payload, settings):
    key = settings.registration_encryption_key.get_secret_value()
    receipt, _ = service.receive(
        session,
        payload,
        key,
        settings.registration_security_ttl_days,
        model=RegistrationReceipt,
    )
    sync_receipt(session, receipt, key)


def confirm(session, token, settings):
    if not isinstance(token, str) or len(token) != 43:
        return False
    receipt = session.scalar(
        select(RegistrationReceipt)
        .where(RegistrationReceipt.token_digest == service.token_hash(token))
        .with_for_update()
    )
    if receipt is None or not service.confirm(
        session, token, model=RegistrationReceipt
    ):
        return False
    sync_receipt(
        session, receipt, settings.registration_encryption_key.get_secret_value()
    )
    return True


def resend(session, row, actor, key):
    if row.status != "awaiting_email":
        raise ValueError("Email confirmation is no longer pending.")
    receipt = session.get(RegistrationReceipt, row.intake_id, with_for_update=True)
    if not receipt:
        raise ValueError(
            "No internal confirmation receipt exists for this registration."
        )
    service.resend(
        session, receipt.id, receipt.revision, key, model=RegistrationReceipt
    )
    sync_receipt(session, receipt, key)
    crm.event(session, row, actor, "confirmation_resend_requested")
