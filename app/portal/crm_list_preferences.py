"""Personal CRM filter visibility and defaults, scoped to the signed-in user."""

import json
import re

from fastapi import APIRouter, HTTPException, Request

from app.domain.models import PortalListPreference, PortalUser
from app.portal.crm_field_catalogue import CATALOGUE, DEFAULT_COLUMNS, field_keys
from app.portal.exception_routes import review_form
from app.portal.routes import DbSession

FIELDS = {
    "mahs": {"q", "archived", "agreement"},
    "contacts": {"q", "archived"},
    "end-users": {"q", "unlinked", "archived"},
    "it-suppliers": {"q"},
    "agreements": {"q", "status", "link", "attachments"},
    "self-declarations": {"q", "year", "assignment", "duplicates"},
}
COLUMNS = {view: field_keys(view) for view in CATALOGUE}
CHOICES = {
    "archived": {"false", "true"},
    "unlinked": {"", "true"},
    "duplicates": {"", "true"},
    "agreement": {"", "linked", "missing", "no-signed"},
    "link": {"", "linked", "unlinked", "ambiguous"},
    "attachments": {"", "missing", "multiple"},
    "assignment": {"", "linked", "unassigned"},
}
router = APIRouter()


def view_fields(view):
    if view not in FIELDS:
        raise HTTPException(404, "CRM list not found.")
    return FIELDS[view]


def validate_preferences(data, fields):
    try:
        visible = json.loads(data.get("visible", "[]"))
        defaults = json.loads(data.get("defaults", "{}"))
        if (
            not isinstance(visible, list)
            or any(not isinstance(name, str) or name not in fields for name in visible)
            or "q" not in visible
            or not isinstance(defaults, dict)
            or set(defaults) != fields
        ):
            raise ValueError()
        for name, value in defaults.items():
            if not isinstance(value, str) or len(value) > 150:
                raise ValueError()
            if name in CHOICES and value not in CHOICES[name]:
                raise ValueError()
            if name == "year" and not re.fullmatch(r"(?:[0-9]{4})?", value):
                raise ValueError()
        return list(dict.fromkeys(visible)), defaults
    except (ValueError, TypeError):
        raise HTTPException(422, "Select valid filter fields and defaults.") from None


def apply_saved_crm_filters(request: Request, session: DbSession):
    from app.portal.crm_views import apply_view_request
    apply_view_request(request, session)


@router.get("/crm/list-preferences/{view}", include_in_schema=False)
def get_preferences(request: Request, view: str, session: DbSession):
    view_fields(view)
    catalogue = [
        {"key": field.key, "label": field.label, "type": field.kind, "origin": field.origin, "operators": field.operators}
        for field in CATALOGUE[view]
    ]
    user = getattr(request.state, "portal_user", None)
    if user is None:
        return {"available": False, "fields": catalogue}
    preference = session.get(PortalListPreference, (user.id, view))
    return {
        "available": True,
        "fields": catalogue,
        "visible": preference.visible if preference else None,
        "defaults": preference.defaults if preference else None,
        "columns": preference.columns if preference else None,
        "column_order": preference.column_order if preference else None,
    }


@router.post("/crm/list-preferences/{view}", include_in_schema=False)
async def save_preferences(request: Request, view: str, session: DbSession):
    fields = view_fields(view)
    user = getattr(request.state, "portal_user", None)
    if user is None:
        raise HTTPException(401, "Sign in to save your list preferences.")
    data = await review_form(request)
    # Serialise saves for one user, including the first creation of a view.
    session.get(PortalUser, user.id, with_for_update=True)
    preference = session.get(PortalListPreference, (user.id, view))
    command = data.get("command", "save")
    if command in {"save-columns", "reset-columns"}:
        columns = None
        column_order = None
        if command == "save-columns":
            try:
                columns = json.loads(data.get("columns", "[]"))
                if (
                    not isinstance(columns, list)
                    or any(not isinstance(name, str) or name not in COLUMNS[view] for name in columns)
                    or COLUMNS[view][0] not in columns
                ):
                    raise ValueError()
                columns = list(dict.fromkeys(columns))
                if "column_order" in data:
                    column_order = json.loads(data["column_order"])
                    if (
                        not isinstance(column_order, list)
                        or any(not isinstance(name, str) for name in column_order)
                        or len(column_order) != len(set(column_order))
                        or not set(DEFAULT_COLUMNS[view]).issubset(column_order)
                        or not set(column_order).issubset(COLUMNS[view])
                    ):
                        raise ValueError()
                    column_order.extend(key for key in COLUMNS[view] if key not in column_order)
            except (ValueError, TypeError):
                raise HTTPException(422, "Select valid columns, including the record name.") from None
        if preference is None:
            preference = PortalListPreference(user_id=user.id, view=view, visible=sorted(fields), defaults={})
            session.add(preference)
        preference.columns = columns
        if command == "reset-columns" or "column_order" in data:
            preference.column_order = column_order
    elif command == "reset":
        if preference:
            if preference.columns is None and preference.column_order is None:
                session.delete(preference)
            else:
                preference.visible = sorted(fields)
                preference.defaults = {}
    elif command == "save":
        visible, defaults = validate_preferences(data, fields)
        if preference is None:
            preference = PortalListPreference(user_id=user.id, view=view)
            session.add(preference)
        preference.visible = visible
        preference.defaults = defaults
    else:
        raise HTTPException(422, "Select a valid list preference action.")
    session.commit()
    return {"saved": True}
