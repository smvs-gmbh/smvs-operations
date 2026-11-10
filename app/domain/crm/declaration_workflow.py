"""Prepare declaration invitations for internal review."""

import hashlib
import hmac
import re
import secrets
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlencode

from sqlalchemy import select

from app.core.db.models import StagingRow
from app.domain.crm.contact_assignments import has_spoc_assignment, spoc_ids
from app.domain.crm.declaration_fees import DEFAULT_BASE_FEE
from app.domain.crm.imports import linked_values
from app.domain.crm.mah_profile import profile_defaults
from app.domain.models import (
    CRMAgreement,
    CRMAgreementMAH,
    CRMContact,
    CRMDeclarationDraft,
    CRMMah,
    CRMSelfDeclaration,
)
from app.integration.artifacts.storage import utcnow

EMAIL = re.compile(r"[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+")
FORM_URL = "https://forms.smvs-gmbh.ch/r/3xqQBG"


def usable_email(value):
    return bool(value and len(value) <= 254 and EMAIL.fullmatch(value))


def unique_emails(addresses):
    unique = {}
    for address in addresses:
        unique.setdefault(address.casefold(), address)
    return list(unique.values())


@dataclass(frozen=True)
class Candidate:
    mah: CRMMah
    recipient_name: str | None
    recipient_emails: tuple[str, ...]
    existing: bool
    imported_suggestion: bool
    signed_contracts: tuple[str, ...]
    recipient_options: tuple[tuple[str, str], ...]


def signed_agreement(mah_id):
    return (
        select(CRMAgreementMAH.agreement_id)
        .join(CRMAgreement)
        .where(CRMAgreementMAH.mah_id == mah_id, CRMAgreement.status == "Signed")
        .exists()
    )


def candidates(session, year, *, lock=False, mah_id=None):
    statement = (
        select(CRMMah, StagingRow.raw_row_json)
        .outerjoin(StagingRow, StagingRow.id == CRMMah.source_row_id)
        .where(CRMMah.archived_at.is_(None), signed_agreement(CRMMah.id))
        .order_by(CRMMah.id)
    )
    if mah_id is not None:
        statement = statement.where(CRMMah.id == mah_id)
    rows = session.execute(statement.with_for_update() if lock else statement).all()
    existing = set(
        session.scalars(
            select(CRMSelfDeclaration.mah_id).where(
                CRMSelfDeclaration.declaration_year == year
            )
        )
    )
    draft_ids = select(CRMDeclarationDraft.mah_id).where(
        CRMDeclarationDraft.data_year == year
    )
    existing.update(session.scalars(draft_ids.with_for_update() if lock else draft_ids))
    imported_contacts = defaultdict(dict)
    for contact, raw in session.execute(
        select(CRMContact, StagingRow.raw_row_json).outerjoin(
            StagingRow, CRMContact.source_row_id == StagingRow.id
        )
    ):
        label = ((raw or {}).get("Record Id") or contact.label).strip().casefold()
        if label:
            imported_contacts[label][contact.id] = contact
    contracts = defaultdict(list)
    for holder_id, contract_id in session.execute(
        select(CRMAgreementMAH.mah_id, CRMAgreement.contract_id)
        .join(CRMAgreement)
        .where(CRMAgreement.status == "Signed")
        .order_by(CRMAgreement.contract_id)
    ):
        contracts[holder_id].append(contract_id)
    result = []
    for mah, source in rows:
        profile = mah.profile or {}
        if not profile.get(
            "eligible_for_invoicing",
            profile_defaults(source or {})["eligible_for_invoicing"],
        ):
            continue
        contacts = [
            session.get(CRMContact, identifier) for identifier in spoc_ids(profile)
        ]
        imported_suggestion = False
        if not has_spoc_assignment(profile):
            references = linked_values((source or {}).get("SPOC", ""))
            matches = [imported_contacts[value.casefold()] for value in references]
            if matches and all(len(match) == 1 for match in matches):
                unique = {
                    identifier: item
                    for match in matches
                    for identifier, item in match.items()
                }
                contacts = list(unique.values())
                imported_suggestion = True
        options = []
        for contact in contacts:
            if contact is None or contact.archived_at or (contact.profile or {}).get("registration_pending"):
                continue
            email = ((contact.profile or {}).get("email", contact.label) or "").strip()
            options.append(
                (contact.display_name[:255], email if usable_email(email) else "")
            )
        name = options[0][0] if len(contacts) == 1 and options else None
        recipients = (
            unique_emails(email for _, email in options if email)
            if not imported_suggestion or len(contacts) == 1
            else []
        )
        result.append(
            Candidate(
                mah,
                name,
                tuple(recipients),
                mah.id in existing,
                imported_suggestion,
                tuple(contracts[mah.id]),
                tuple(options),
            )
        )
    return sorted(result, key=lambda item: (item.mah.name.casefold(), item.mah.id))


def invitation_code(secret, nonce):
    return hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()


def create_drafts(session, year, secret):
    created = 0
    for candidate in candidates(session, year, lock=True):
        if candidate.existing:
            continue
        nonce = secrets.token_hex(32)
        digest = hashlib.sha256(invitation_code(secret, nonce).encode()).hexdigest()
        session.add(
            CRMDeclarationDraft(
                mah_id=candidate.mah.id,
                data_year=year,
                base_fee=DEFAULT_BASE_FEE,
                recipient_name=candidate.recipient_name,
                recipient_emails=list(candidate.recipient_emails),
                token_nonce=nonce,
                token_digest=digest,
                created_at=utcnow(),
            )
        )
        created += 1
    return created


def invitation_url(draft, mah, secret, *, form_url=FORM_URL):
    code = invitation_code(secret, draft.token_nonce)
    if not hmac.compare_digest(
        hashlib.sha256(code.encode()).hexdigest(), draft.token_digest
    ):
        return None
    return (
        form_url
        + "?"
        + urlencode({"auth_code": code, "year": draft.data_year, "account": mah.name})
    )
