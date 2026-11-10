"""Administrator deletion review with an explicit, visible scope."""

from sqlalchemy import select

from app.domain.crm.deletion import contact_assignment_owners
from app.domain.models import CRMContact, CRMEndUser, EndUserRegistration
from app.portal.routes import templates


def render_deletion_review(
    request, session, row, record_type, error=None, status_code=200
):
    if isinstance(row, EndUserRegistration):
        registrations = [row]
        back_url = f"/workflows/registrations/{row.id}"
        label = f"Registration #{row.id}"
    else:
        registrations = []
        if isinstance(row, (CRMEndUser, CRMContact)):
            column = (
                EndUserRegistration.end_user_id
                if isinstance(row, CRMEndUser)
                else EndUserRegistration.contact_id
            )
            registrations = session.scalars(
                select(EndUserRegistration)
                .where(column == row.id)
                .order_by(EndUserRegistration.id)
            ).all()
        back_url = f"/crm/{record_type}/{row.id}"
        label = row.display_name if isinstance(row, CRMContact) else row.name
    scope = []
    for registration in registrations:
        user = (
            session.get(CRMEndUser, registration.end_user_id)
            if registration.end_user_id
            else None
        )
        contact = (
            session.get(CRMContact, registration.contact_id)
            if registration.contact_id
            else None
        )
        scope.append((registration, user, contact))
    return templates.TemplateResponse(
        request=request,
        name="crm_delete_review.html",
        status_code=status_code,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "same-origin"},
        context={
            "title": "Review permanent deletion",
            "active": "crm" if record_type else "workflows",
            "label": label,
            "back_url": back_url,
            "delete_type": record_type,
            "delete_record": row,
            "registration_scope": scope,
            "contact_owners": contact_assignment_owners(session, row.id)
            if isinstance(row, CRMContact)
            else [],
            "error": error,
        },
    )
