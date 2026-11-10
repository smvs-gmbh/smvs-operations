"""Personal CRM working lists and shared evaluation before pagination."""

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.domain.models import CRMListView, PortalListPreference, PortalUser
from app.integration.artifacts.storage import utcnow
from app.portal.crm_field_catalogue import CATALOGUE, DEFAULT_COLUMNS, catalogue_context
from app.portal.crm_list_preferences import FIELDS, validate_preferences
from app.portal.exception_routes import review_form
from app.portal.queries import PAGE_SIZE, paged
from app.portal.record_navigation import list_record_navigation, record_navigation
from app.portal.routes import DbSession

router = APIRouter()
CHECKBOX_FILTERS = {"unlinked", "duplicates"}


def default_quick(directory):
    return {key: "false" if key == "archived" else "" for key in FIELDS[directory]}


def normalise_config(directory, config):
    if not isinstance(config, dict):
        raise HTTPException(422, "Enter valid view settings.")
    fields = {field.key: field for field in CATALOGUE[directory]}
    quick = config.get("quick_filters", {})
    if not isinstance(quick, dict) or not set(quick).issubset(FIELDS[directory]):
        raise HTTPException(422, "Select valid quick filters.")
    quick = default_quick(directory) | quick
    _, quick = validate_preferences(
        {
            "visible": json.dumps(sorted(FIELDS[directory])),
            "defaults": json.dumps(quick),
        },
        FIELDS[directory],
    )
    conditions = config.get("conditions", [])
    if not isinstance(conditions, list) or len(conditions) > 12:
        raise HTTPException(422, "Use up to 12 conditions, combined with AND.")
    cleaned = []
    for condition in conditions:
        if (
            not isinstance(condition, dict)
            or not isinstance(condition.get("field"), str)
            or condition["field"] not in fields
        ):
            raise HTTPException(422, "Select a field from this directory.")
        field = fields[condition["field"]]
        operator = condition.get("operator")
        if operator not in field.operators:
            raise HTTPException(422, "Select an operator supported by the field.")
        value = condition.get("value", "")
        try:
            if operator in {"empty", "not_empty"}:
                value = ""
            elif field.kind == "boolean":
                if not (
                    type(value) is bool
                    or isinstance(value, str)
                    and value in {"true", "false"}
                ):
                    raise ValueError()
                value = value is True or value == "true"
            elif field.kind == "number":
                number = Decimal(str(value))
                if not number.is_finite() or len(str(value)) > 80:
                    raise ValueError()
                value = str(number)
            elif field.kind == "date":
                value = date.fromisoformat(value).isoformat()
            elif not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError()
            else:
                value = value.strip()
        except (ValueError, TypeError, InvalidOperation):
            raise HTTPException(
                422, f"Enter a valid value for {field.label}."
            ) from None
        cleaned.append({"field": field.key, "operator": operator, "value": value})
    columns = config.get("columns")
    if columns is not None and (
        not isinstance(columns, list)
        or any(not isinstance(key, str) or key not in fields for key in columns)
        or DEFAULT_COLUMNS[directory][0] not in columns
    ):
        raise HTTPException(422, "Select valid columns, including the record name.")
    order = config.get("column_order")
    if order is not None:
        if (
            not isinstance(order, list)
            or any(not isinstance(key, str) or key not in fields for key in order)
            or len(order) != len(set(order))
            or not set(DEFAULT_COLUMNS[directory]).issubset(order)
        ):
            raise HTTPException(422, "Select a valid column order.")
        order = order + [key for key in fields if key not in order]
    sort = config.get("sort", "") or ""
    direction = config.get("direction", "asc")
    if (
        not isinstance(sort, str)
        or sort not in {"", *fields}
        or not isinstance(direction, str)
        or direction not in {"asc", "desc"}
    ):
        raise HTTPException(422, "Select a valid sort field and direction.")
    return {
        "quick_filters": quick,
        "conditions": cleaned,
        "columns": list(dict.fromkeys(columns)) if columns is not None else None,
        "column_order": order,
        "sort": sort,
        "direction": direction,
    }


def own_view(session, user, directory, identifier):
    if (
        user is None
        or not str(identifier).isdigit()
        or len(str(identifier)) > 19
        or int(identifier) > 2**63 - 1
    ):
        raise HTTPException(404, "View not found.")
    row = session.scalar(
        select(CRMListView).where(
            CRMListView.id == int(identifier),
            CRMListView.user_id == user.id,
            CRMListView.directory == directory,
        )
    )
    if row is None:
        raise HTTPException(404, "View not found.")
    return row


def resolve_view(request, session, directory):
    user = getattr(request.state, "portal_user", None)
    selected = request.query_params.get("view")
    row = (
        own_view(session, user, directory, selected)
        if selected not in (None, "all")
        else None
    )
    preference = (
        session.get(PortalListPreference, (user.id, directory)) if user else None
    )
    config = (
        row.config
        if row
        else {
            "columns": preference.columns if preference and selected != "all" else None,
            "column_order": preference.column_order
            if preference and selected != "all"
            else None,
        }
    )
    config = dict(config)
    quick = default_quick(directory) | config.get("quick_filters", {})
    for key in FIELDS[directory]:
        if key in request.query_params:
            value = request.query_params[key]
            if key in CHECKBOX_FILTERS:
                value = "true" if value.lower() in {"true", "1", "yes", "on"} else ""
            if key == "archived":
                value = (
                    "true" if value.lower() in {"true", "1", "yes", "on"} else "false"
                )
            quick[key] = value
    config["quick_filters"] = quick
    if "rules" in request.query_params:
        try:
            raw = request.query_params["rules"]
            if len(raw) > 10000:
                raise ValueError()
            config["conditions"] = json.loads(raw)
        except ValueError:
            raise HTTPException(422, "Enter valid view conditions.") from None
    if "layout" in request.query_params:
        try:
            raw = request.query_params["layout"]
            if len(raw) > 10000:
                raise ValueError()
            layout = json.loads(raw)
            if not isinstance(layout, dict) or not set(layout).issubset(
                {"columns", "column_order"}
            ):
                raise ValueError()
            config.update(layout)
        except ValueError:
            raise HTTPException(422, "Select valid view columns.") from None
    for key in ("sort", "direction"):
        if key in request.query_params:
            config[key] = request.query_params[key]
    return row, normalise_config(directory, config)


def apply_view_request(request, session):
    if request.method != "GET":
        return
    parts = request.url.path.strip("/").split("/")
    if len(parts) < 2 or parts[0] != "crm" or parts[1] not in FIELDS:
        return
    directory = parts[1]
    # Older view URLs encoded unchecked checkboxes as an empty boolean value.
    # Redirect before FastAPI validates the endpoint's typed query parameters.
    checkbox_filters = CHECKBOX_FILTERS & FIELDS[directory]
    if any(request.query_params.get(key) == "" for key in checkbox_filters):
        query = [
            (key, "false" if key in checkbox_filters and value == "" else value)
            for key, value in request.query_params.multi_items()
        ]
        raise HTTPException(
            303, headers={"Location": request.url.path + "?" + urlencode(query)}
        )
    user = getattr(request.state, "portal_user", None)
    if len(parts) == 2 and not request.query_params and user:
        default = session.scalar(
            select(CRMListView).where(
                CRMListView.user_id == user.id,
                CRMListView.directory == directory,
                CRMListView.is_default == 1,
            )
        )
        if default:
            raise HTTPException(
                303, headers={"Location": f"/crm/{directory}?view={default.id}"}
            )
    row, config = resolve_view(request, session, directory)
    request.state.crm_view_config = config
    if row:
        merged = {
            key: value
            for key, value in config["quick_filters"].items()
            if value != "" or key == "q"
        }
        merged.update(request.query_params)
        if merged != dict(request.query_params):
            raise HTTPException(
                303, headers={"Location": request.url.path + "?" + urlencode(merged)}
            )


def view_json(row):
    return {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "is_default": bool(row.is_default),
        "config": normalise_config(row.directory, row.config),
    }


def presets(directory):
    if directory != "mahs":
        return []
    return [
        {
            "id": "no-agreement",
            "name": "No agreement",
            "config": {"quick_filters": {"agreement": "missing"}},
        },
        {
            "id": "no-signed-agreement",
            "name": "No signed agreement",
            "config": {"quick_filters": {"agreement": "no-signed"}},
        },
        {
            "id": "declaration-ready",
            "name": "Ready for self-declaration",
            "config": {
                "conditions": [
                    {"field": "contract", "operator": "contains", "value": "Signed"},
                    {
                        "field": "eligible_for_invoicing",
                        "operator": "equals",
                        "value": True,
                    },
                ]
            },
        },
    ]


@router.get("/crm/views/{directory}", include_in_schema=False)
def views(request: Request, directory: str, session: DbSession):
    if directory not in FIELDS:
        raise HTTPException(404, "CRM directory not found.")
    user = getattr(request.state, "portal_user", None)
    row, config = resolve_view(request, session, directory)
    saved = (
        list(
            session.scalars(
                select(CRMListView)
                .where(
                    CRMListView.user_id == user.id,
                    CRMListView.directory == directory,
                )
                .order_by(CRMListView.name, CRMListView.id)
            )
        )
        if user
        else []
    )
    return {
        "available": bool(user),
        "views": [view_json(item) for item in saved],
        "selected": view_json(row) if row else None,
        "config": config,
        "presets": presets(directory),
    }


@router.post("/crm/views/{directory}", include_in_schema=False)
async def save_view(request: Request, directory: str, session: DbSession):
    if directory not in FIELDS:
        raise HTTPException(404, "CRM directory not found.")
    data = await review_form(request)
    try:
        config = normalise_config(directory, json.loads(data.get("config", "{}")))
    except ValueError:
        raise HTTPException(422, "Enter valid view settings.") from None
    command = data.get("command", "save")
    if command == "preview":
        return {"config": config}
    user = getattr(request.state, "portal_user", None)
    if user is None:
        raise HTTPException(401, "Sign in to save a view.")
    session.get(PortalUser, user.id, with_for_update=True)
    row = (
        own_view(session, user, directory, data["id"])
        if data.get("id") and command != "create"
        else None
    )
    if row and data.get("version") != str(row.version):
        raise HTTPException(409, "This view changed. Reload before saving.")
    if command == "delete":
        if row is None:
            raise HTTPException(404, "View not found.")
        session.delete(row)
    elif command in {"save", "create"}:
        name = data.get("name", "").strip()
        if not name or len(name) > 80:
            raise HTTPException(422, "Enter a view name of up to 80 characters.")
        existing = list(
            session.scalars(
                select(CRMListView).where(
                    CRMListView.user_id == user.id,
                    CRMListView.directory == directory,
                )
            )
        )
        if any(
            item.name.casefold() == name.casefold()
            and (row is None or item.id != row.id)
            for item in existing
        ):
            raise HTTPException(409, "You already have a view with this name.")
        if row is None:
            if len(existing) >= 100:
                raise HTTPException(422, "Keep up to 100 personal views per directory.")
            row = CRMListView(
                user_id=user.id, directory=directory, name=name, created_at=utcnow()
            )
            session.add(row)
        is_default = data.get("is_default") == "true"
        if is_default:
            for item in existing:
                if item.id != row.id and item.is_default:
                    item.is_default = 0
                    item.updated_at = utcnow()
        row.name, row.config, row.is_default, row.updated_at = (
            name,
            config,
            int(is_default),
            utcnow(),
        )
    else:
        raise HTTPException(422, "Select a valid view action.")
    try:
        session.commit()
    except (IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(409, "This view changed. Reload before saving.") from None
    return {"view": view_json(row) if command != "delete" else None}


def empty(value):
    return value is None or value == "" or value == []


def matches(value, condition, field):
    operator, expected = condition["operator"], condition["value"]
    if operator == "empty":
        return empty(value)
    if operator == "not_empty":
        return not empty(value)
    if empty(value):
        return False
    if field.kind == "list":
        return str(expected).casefold() in {str(item).casefold() for item in value}
    if field.kind == "boolean":
        return bool(value) == expected
    if field.kind == "number":
        value, expected = Decimal(str(value)), Decimal(expected)
    elif field.kind == "date":
        value = value.date() if isinstance(value, datetime) else value
        value, expected = date.fromisoformat(str(value)), date.fromisoformat(expected)
    else:
        value, expected = str(value).casefold(), str(expected).casefold()
    if operator == "contains":
        return expected in value
    if operator in {"less_than", "before"}:
        return value < expected
    if operator in {"greater_than", "after"}:
        return value > expected
    return value == expected


def configured_rows(request, session, directory, records, *, pdf_counts=None):
    config = getattr(request.state, "crm_view_config", {})
    conditions, sort = config.get("conditions", []), config.get("sort", "")
    if not conditions and not sort:
        return records
    context = catalogue_context(session, directory, records, pdf_counts=pdf_counts)
    request.state.crm_catalogue_context = context
    values = context["crm_field_values"]
    fields = {field.key: field for field in CATALOGUE[directory]}
    selected = [
        record
        for record in records
        if all(
            matches(
                values[record.id][condition["field"]],
                condition,
                fields[condition["field"]],
            )
            for condition in conditions
        )
    ]
    if sort:
        present = [record for record in selected if not empty(values[record.id][sort])]
        missing = [record for record in selected if empty(values[record.id][sort])]

        def sort_key(record):
            value = values[record.id][sort]
            if fields[sort].kind == "number":
                return Decimal(str(value))
            if fields[sort].kind == "boolean":
                return bool(value)
            if isinstance(value, (list, tuple)):
                return ", ".join(sorted(str(item).casefold() for item in value))
            return str(value).casefold()

        present.sort(key=sort_key, reverse=config["direction"] == "desc")
        selected = present + missing
    return selected


def crm_paged(session, statement, page, request, directory, *, pdf_counts=None):
    config = getattr(request.state, "crm_view_config", {})
    if not config.get("conditions") and not config.get("sort"):
        return paged(session, statement, page)
    rows = session.execute(statement).all()
    selected = configured_rows(
        request, session, directory, [row[0] for row in rows], pdf_counts=pdf_counts
    )
    by_id = {row[0].id: row for row in rows}
    total = len(selected)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    start = (page - 1) * PAGE_SIZE
    return [by_id[record.id] for record in selected[start : start + PAGE_SIZE]], {
        "page": page,
        "pages": pages,
        "total": total,
        "first": start + 1 if total else 0,
        "last": min(start + PAGE_SIZE, total),
    }


def list_catalogue_context(request, session, directory, records, *, pdf_counts=None):
    cached = getattr(request.state, "crm_catalogue_context", None)
    return (
        cached
        if cached is not None
        else catalogue_context(session, directory, records, pdf_counts=pdf_counts)
    )


def crm_navigation(
    request,
    session,
    statement,
    column,
    identifier,
    ordering,
    path,
    label,
    *,
    pdf_counts=None,
    **urls,
):
    config = getattr(request.state, "crm_view_config", {})
    if not config.get("conditions") and not config.get("sort"):
        return list_record_navigation(
            session, statement, column, identifier, ordering, path, label, **urls
        )
    rows = session.execute(statement.order_by(*ordering)).all()
    directory = path.rsplit("/", 1)[-1]
    selected = configured_rows(
        request, session, directory, [row[0] for row in rows], pdf_counts=pdf_counts
    )
    ids = [record.id for record in selected]
    position = ids.index(identifier) if identifier in ids else None
    previous = ids[position - 1] if position is not None and position > 0 else None
    following = (
        ids[position + 1] if position is not None and position + 1 < len(ids) else None
    )
    return record_navigation(path, label, previous, following, **urls)
