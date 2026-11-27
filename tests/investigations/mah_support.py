"""Explicit staff requests for tests exercising exceptional MAH workflows."""
from sqlalchemy import select

from app.domain.investigations import pilot
from app.domain.models import (
    AlertDeskResponseRequest,
    CRMMah,
    NMVSException,
    PortalUser,
)


def request_mah_review(factory, identifiers):
    with factory.begin() as session:
        actor = session.scalar(select(PortalUser))
        if actor is None:
            actor = PortalUser(email="reviewer@example.test", handle="mah-reviewer", is_admin=1, is_nmvo=1)
            session.add(actor); session.flush()
        crm = session.scalar(select(CRMMah))
        for identifier in identifiers:
            record = session.get(NMVSException, identifier)
            session.add(AlertDeskResponseRequest(exception_id=identifier, role="mah", crm_organisation_id=crm.id, source_version=record.payload_hash, after_event_id=0, actor_id=actor.id, requested_at=pilot.now(), due_on=pilot.now().date()))
