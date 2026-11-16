"""CRM membership and organisation-wide pilot access."""

import hmac
import secrets
from datetime import timedelta

from sqlalchemy import and_, case, func, or_, select

from app.domain.investigations import audience, pilot, rca
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskEvent,
    AlertDeskExportAttribution,
    AlertDeskGrant,
    CRMContact,
    CRMEndUser,
    CRMMah,
    CurrentPublication,
    LocalLocation,
    LocalOrganisation,
    NMVSException,
    SAIHolder,
    SAIPackage,
    SAIPreparation,
)

DIRECTORIES = {"end_user": CRMEndUser, "mah": CRMMah}
PAGE_SIZE = 50


def scope_key(role, crm):
    return str(crm.organisation_id or "") if role == "end_user" else (crm.gln or "")


def membership(session, access):
    model = DIRECTORIES[access.role]
    crm = session.get(model, access.crm_organisation_id)
    contact = session.get(CRMContact, access.contact_id)
    if (
        crm
        and not crm.archived_at
        and contact
        and not contact.archived_at
        and contact.version == access.contact_version
        and scope_key(access.role, crm) == access.scope_key
        and contact.id in (crm.profile or {}).get("alert_contact_ids", [])
    ):
        email = (contact.profile or {}).get("email")
        if audience.deliverable(email):
            return crm, email
    return None


def issue(session, role, organisation, contact, actor_id):
    grant = session.scalar(
        select(AlertDeskAccess)
        .where(
            AlertDeskAccess.role == role,
            AlertDeskAccess.crm_organisation_id == organisation.id,
            AlertDeskAccess.contact_id == contact.id,
        )
        .with_for_update()
    )
    now = pilot.now()
    if (
        grant
        and grant.contact_version == contact.version
        and grant.scope_key == scope_key(role, organisation)
        and not grant.revoked_at
        and (
            (grant.invite_hash and grant.invite_expires_at > now)
            or (
                grant.session_hash
                and grant.session_expires_at
                and grant.session_expires_at > now
            )
        )
    ):
        return None
    token = secrets.token_urlsafe(32)
    if not grant:
        grant = AlertDeskAccess(
            role=role, crm_organisation_id=organisation.id, contact_id=contact.id
        )
        session.add(grant)
    grant.contact_version = contact.version
    grant.scope_key = scope_key(role, organisation)
    grant.invited_by = actor_id
    grant.invited_at = now
    grant.sent_at = grant.accepted_at = grant.revoked_at = None
    grant.invite_hash = pilot.digest(token)
    grant.invite_expires_at = now + timedelta(hours=24)
    grant.challenge_hash = grant.code_hash = grant.code_expires_at = None
    grant.session_hash = grant.session_expires_at = None
    grant.attempts_left = 0
    session.flush()
    return grant, token


def lookup(session, column, token, *, lock=False):
    statement = select(AlertDeskAccess).where(column == pilot.digest(token))
    grant = session.scalar(statement.with_for_update() if lock else statement)
    if not grant or grant.revoked_at or not grant.sent_at:
        return None
    linked = membership(session, grant)
    return (grant, *linked) if linked else None


def code_hash(secret, challenge, code):
    return hmac.digest(
        secret.encode(), f"alert-desk:{challenge}:{code}".encode(), "sha256"
    ).hex()


def cases(session, role, crm, namespace):
    statement = select(NMVSException).where(NMVSException.source_namespace == namespace)
    if role == "end_user":
        org = (
            session.get(LocalOrganisation, crm.organisation_id)
            if crm.organisation_id
            else None
        )
        attribution = AlertDeskExportAttribution
        reviewed_exports = and_(
            NMVSException.error_code == "A7",
            NMVSException.evidence["attemptedOperation"].as_string() == "EXPORTED",
            NMVSException.business_process == "National System Intermarket",
            NMVSException.organisation_id.is_(None),
            select(
                case(
                    (
                        func.count(func.distinct(attribution.end_user_id)) == 1,
                        func.max(attribution.end_user_id),
                    )
                )
            )
            .where(
                attribution.source_namespace == NMVSException.source_namespace,
                attribution.source_market == NMVSException.source_market,
                attribution.source_location_id == NMVSException.source_location_id,
                attribution.gtin14 == NMVSException.gtin14,
                attribution.batch == NMVSException.provided_batch,
                NMVSException.alert_at >= attribution.from_at,
                NMVSException.alert_at < attribution.until_at,
            )
            .scalar_subquery()
            == crm.id,
        )
        if not org or not org.is_observed or org.source_namespace != namespace:
            return statement.where(reviewed_exports)
        locations = select(LocalLocation.source_location_id).where(
            LocalLocation.source_namespace == namespace,
            LocalLocation.organisation_id == org.id,
            LocalLocation.is_observed == 1,
        )
        return statement.where(
            or_(
                reviewed_exports,
                and_(
                    NMVSException.source_market.in_(("CH", "LI")),
                    NMVSException.organisation_id == org.source_organisation_id,
                    or_(
                        and_(
                            NMVSException.source_market == "CH",
                            NMVSException.source_location_id.is_(None),
                        ),
                        NMVSException.source_location_id.in_(locations),
                    ),
                ),
            )
        )
    publication = session.get(CurrentPublication, "product-batch")
    if not publication or publication.source_namespace != namespace or not crm.gln:
        return statement.where(False)
    same_gln = session.scalar(
        select(func.count())
        .select_from(CRMMah)
        .where(CRMMah.gln == crm.gln, CRMMah.archived_at.is_(None))
    )
    if same_gln != 1:
        return statement.where(False)
    packages = (
        select(SAIPackage.gtin14)
        .select_from(SAIPackage)
        .outerjoin(SAIPreparation, SAIPackage.preparation_id == SAIPreparation.id)
        .outerjoin(SAIHolder, SAIPreparation.holder_id == SAIHolder.id)
        .where(
            SAIPackage.is_observed == 1,
            SAIPackage.last_mapping_run_id == publication.mapping_run_id,
        )
        .group_by(SAIPackage.gtin14)
        .having(
            func.count() == 1,
            func.max(SAIHolder.gln) == crm.gln,
            func.max(SAIHolder.is_observed) == 1,
        )
    )
    return statement.where(
        NMVSException.gtin14.in_(packages),
        or_(NMVSException.source_market.is_(None), NMVSException.source_market != "LI"),
    )


def export_cohort(session, record, *, end_user_id=None, lock=False):
    if (
        record.error_code != "A7"
        or record.organisation_id is not None
        or record.business_process != "National System Intermarket"
        or (record.evidence or {}).get("attemptedOperation") != "EXPORTED"
        or not record.alert_at
    ):
        return None
    attribution = AlertDeskExportAttribution
    query = select(attribution).where(
        attribution.source_namespace == record.source_namespace,
        attribution.source_market == record.source_market,
        attribution.source_location_id == record.source_location_id,
        attribution.gtin14 == record.gtin14,
        attribution.batch == record.provided_batch,
        record.alert_at >= attribution.from_at,
        record.alert_at < attribution.until_at,
    )
    if end_user_id is not None:
        query = query.where(attribution.end_user_id == end_user_id)
    query = query.order_by(attribution.id).limit(2)
    cohorts = session.scalars(query.with_for_update() if lock else query).all()
    return cohorts[0] if len(cohorts) == 1 else None


def batch_targets(session, role, crm, record, *, lock=False):
    """Return pending alerts with the same actionable batch context."""
    query = cases(session, role, crm, record.source_namespace).where(
        NMVSException.id != record.id,
        NMVSException.error_code == record.error_code,
        ~rca.closed_condition(),
    )
    if record.error_code == "A2":
        operation = (record.evidence or {}).get("attemptedOperation")
        if not (
            record.source_market in {"CH", "LI"}
            and (record.source_market != "LI" or role == "end_user")
            and record.is_intermarket in {0, 1}
            and record.organisation_id
            and record.source_location_id
            and record.gtin14
            and record.provided_batch
            and operation
        ):
            return []
        query = query.where(
            NMVSException.source_market == record.source_market,
            NMVSException.organisation_id == record.organisation_id,
            NMVSException.source_location_id == record.source_location_id,
            NMVSException.gtin14 == record.gtin14,
            NMVSException.provided_batch == record.provided_batch,
            NMVSException.is_intermarket == record.is_intermarket,
            NMVSException.business_process == record.business_process,
            NMVSException.evidence["attemptedOperation"].as_string() == operation,
        )
    else:
        cohort = export_cohort(
            session, record, end_user_id=crm.id if role == "end_user" else None, lock=lock
        )
        if not cohort:
            return []
        query = query.where(
            NMVSException.evidence["attemptedOperation"].as_string() == "EXPORTED",
            NMVSException.source_market == cohort.source_market,
            NMVSException.source_location_id == cohort.source_location_id,
            NMVSException.gtin14 == cohort.gtin14,
            NMVSException.provided_batch == cohort.batch,
            NMVSException.alert_at >= cohort.from_at,
            NMVSException.alert_at < cohort.until_at,
            NMVSException.organisation_id.is_(None),
            NMVSException.business_process == "National System Intermarket",
        )
    query = query.order_by(NMVSException.id)
    targets = session.scalars(query.with_for_update() if lock else query).all()
    if not targets:
        return []
    existing = (
        select(AlertDeskGrant.exception_id, AlertDeskEvent.data["finding"].as_string())
        .join(AlertDeskEvent, AlertDeskEvent.grant_id == AlertDeskGrant.id)
        .join(
            AlertDeskAccess,
            AlertDeskGrant.publication["organisation_access"].as_integer()
            == AlertDeskAccess.id,
        )
        .join(NMVSException, NMVSException.id == AlertDeskGrant.exception_id)
        .where(
            AlertDeskGrant.exception_id.in_([target.id for target in targets]),
            AlertDeskGrant.source_version == NMVSException.payload_hash,
            AlertDeskEvent.kind == "Findings submitted",
            AlertDeskAccess.role == role,
            AlertDeskAccess.crm_organisation_id == crm.id,
        )
        .order_by(AlertDeskEvent.id.desc())
    )
    latest = {}
    for identifier, finding in session.execute(
        existing.with_for_update() if lock else existing
    ):
        latest.setdefault(identifier, finding)
    return [
        target
        for target in targets
        if target.id not in latest or latest[target.id] == "investigating"
    ]


def batch_revision(records):
    return pilot.digest(
        "|".join(f"{record.id}:{record.payload_hash}" for record in records)
    )
