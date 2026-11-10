"""Personal table views. SQL directories filter before counting/paging.

Other tables describe their already scoped report in the browser; their views
never request additional data or change the underlying evidence/actions.
"""

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.domain.models import CRMListView, PortalUser
from app.integration.artifacts.storage import utcnow
from app.portal.crm_field_catalogue import CRMField
from app.portal.exception_routes import review_form
from app.portal.routes import DbSession

router = APIRouter()
SQL_KEYS = {
    "registrations",
    "products",
    "batches",
    "organisations",
    "locations",
    "exceptions",
    "product-batches",
    "organisation-locations",
}


def sql_fields(key):
    if key == "product-batches":
        fields = sql_fields("batches")
        return [fields[0], *fields[2:]]
    if key == "organisation-locations":
        fields = sql_fields("locations")
        return [fields[0], *fields[2:]]
    from app.domain.models import (
        Batch,
        CRMContact,
        CRMEndUser,
        EndUserRegistration,
        Product,
    )
    from app.domain.models import (
        ExceptionReview as R,
    )
    from app.domain.models import (
        LocalLocation as L,
    )
    from app.domain.models import (
        LocalOrganisation as O,
    )
    from app.domain.models import (
        NMVSException as E,
    )
    from app.domain.models import (
        ProductReferenceMatch as M,
    )
    from app.domain.models import (
        ProductSourceRecord as P,
    )
    from app.domain.models import (
        SAIHolder as H,
    )
    from app.domain.models import (
        SAIPackage as Pack,
    )
    from app.domain.models import (
        SAIPreparation as S,
    )

    def joined(*columns):
        value = func.coalesce(cast(columns[0], String), "")
        for column in columns[1:]:
            value = value + " " + func.coalesce(cast(column, String), "")
        return value

    swiss_name = (
        select(S.preparation_name)
        .select_from(P)
        .join(Product, P.product_id == Product.id)
        .outerjoin(M, M.product_id == Product.id)
        .outerjoin(Pack, M.sai_package_id == Pack.id)
        .outerjoin(S, Pack.preparation_id == S.id)
        .where(
            P.source_namespace == E.source_namespace,
            P.is_observed == 1,
            Product.gtin14 == E.gtin14,
        )
        .correlate(E)
        .limit(1)
        .scalar_subquery()
    )
    organisation_name = (
        select(O.organisation_name)
        .where(
            O.source_namespace == E.source_namespace,
            O.source_organisation_id == E.organisation_id,
        )
        .correlate(E)
        .limit(1)
        .scalar_subquery()
    )
    work_status = case(
        (R.basis_payload_hash != E.payload_hash, "Needs review"),
        else_=func.coalesce(R.status, "open"),
    )
    return {
        "registrations": [
            (CRMEndUser.name, "text"),
            (
                joined(
                    CRMContact.profile["first_name"].as_string(),
                    CRMContact.profile["last_name"].as_string(),
                    CRMContact.profile["email"].as_string(),
                ),
                "text",
            ),
            (
                case(
                    *[
                        (EndUserRegistration.status == k, v)
                        for k, v in {
                            "awaiting_email": "Awaiting email confirmation",
                            "needs_review": "Needs review",
                            "ready_nmvs": "Ready for NMVS",
                            "nmvs_created": "NMVS created",
                            "rejected": "Rejected",
                            "expired": "Expired before import",
                        }.items()
                    ],
                    else_=EndUserRegistration.status,
                ),
                "text",
            ),
            (func.date(EndUserRegistration.received_at), "date"),
            (func.date(EndUserRegistration.confirmed_at), "date"),
        ],
        "products": [
            (S.preparation_name, "text"),
            (Product.gtin14, "text"),
            (H.company_name, "text"),
            (P.reported_version, "number"),
            (M.match_status, "text"),
        ],
        "batches": [
            (Batch.batch_code, "text"),
            (S.preparation_name, "text"),
            (Batch.evidence["Product Version Number"].as_string(), "text"),
            (Batch.expiry_source_text, "text"),
            (Batch.batch_state, "text"),
            (Batch.pack_count, "number"),
            (Batch.active_pack_count, "number"),
        ],
        "organisations": [
            (O.organisation_name, "text"),
            (joined(O.organisation_type, O.organisation_subtype), "text"),
            (O.organisation_status, "text"),
            (
                select(func.count())
                .select_from(L)
                .where(L.organisation_id == O.id)
                .correlate(O)
                .scalar_subquery(),
                "number",
            ),
        ],
        "locations": [
            (L.location_name, "text"),
            (O.organisation_name, "text"),
            (joined(L.city, L.postal_code), "text"),
            (L.location_status, "text"),
            (L.equipment_count, "number"),
        ],
        "exceptions": [
            (E.unique_alert_id, "text"),
            (work_status, "text"),
            (E.error_code, "text"),
            (joined(swiss_name, E.gtin14), "text"),
            (joined(E.provided_batch, E.stored_batch, E.serial_number), "text"),
            (
                joined(
                    organisation_name,
                    E.source_market,
                    E.business_process,
                    E.source_location_id,
                ),
                "text",
            ),
        ],
    }[key]


def schema_for(request, key):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,33}", key):
        raise HTTPException(404, "Table not found.")
    try:
        raw = request.query_params.get("schema", "[]")
        if len(raw) > 16000:
            raise ValueError()
        schema = json.loads(raw)
        if not isinstance(schema, list) or not 1 <= len(schema) <= 100:
            raise ValueError()
        seen = set()
        for field in schema:
            if (
                not isinstance(field, dict)
                or not re.fullmatch(r"(c[0-9]{1,3}|selection)", field.get("key", ""))
                or field["key"] in seen
                or not isinstance(field.get("label"), str)
                or len(field["label"]) > 200
            ):
                raise ValueError()
            seen.add(field["key"])
            field["type"] = (
                field.get("type", "text")
                if field.get("type") in ("text", "number", "date")
                else "text"
            )
            field["column_only"] = (
                bool(field.get("column_only")) or field["key"] == "selection"
            )
        if key in SQL_KEYS:
            expressions = sql_fields(key)
            for field in schema:
                if field["key"].startswith("c"):
                    i = int(field["key"][1:])
                    field["column_only"] = i >= len(expressions)
                    if i < len(expressions):
                        field["type"] = expressions[i][1]
        if key == "exceptions" and "selection" not in seen:
            schema.append(
                {
                    "key": "selection",
                    "label": "Selection",
                    "type": "text",
                    "column_only": True,
                }
            )
        return schema
    except (ValueError, TypeError, KeyError):
        raise HTTPException(422, "Invalid table definition.") from None


def normalise(config, schema):
    if not isinstance(config, dict):
        raise HTTPException(422, "Invalid view settings.")
    fields = {f["key"]: f for f in schema}
    keys = list(fields)
    columns = config.get("columns") or keys
    order = config.get("column_order") or keys
    conditions = config.get("conditions", [])
    quick = config.get("quick_filters", {})
    try:
        if (
            not isinstance(columns, list)
            or not set(columns) <= fields.keys()
            or "c0" not in columns
            or not isinstance(order, list)
            or not set(order) <= fields.keys()
            or len(order) != len(set(order))
            or not isinstance(conditions, list)
            or len(conditions) > 12
            or not isinstance(quick, dict)
            or len(quick) > 40
            or any(
                not re.fullmatch(r"[a-z_]{1,40}", k)
                or not isinstance(v, str)
                or len(v) > 1500
                for k, v in quick.items()
            )
        ):
            raise ValueError()
        cleaned = []
        for c in conditions:
            f = fields[c["field"]]
            kind = f["type"]
            operator = c["operator"]
            value = c.get("value", "")
            if f.get("column_only") or operator not in CRMField("", "", kind).operators:
                raise ValueError()
            if operator in ("empty", "not_empty"):
                value = ""
            elif kind == "number":
                value = str(Decimal(str(value)))
                if not Decimal(value).is_finite():
                    raise ValueError()
            elif kind == "date":
                value = date.fromisoformat(value).isoformat()
            elif not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError()
            cleaned.append({"field": c["field"], "operator": operator, "value": value})
        sort = config.get("sort", "") or ""
        direction = config.get("direction", "asc")
        if (
            sort and (sort not in fields or fields[sort].get("column_only"))
        ) or direction not in ("asc", "desc"):
            raise ValueError()
        return {
            "quick_filters": quick,
            "conditions": cleaned,
            "columns": list(dict.fromkeys(columns)),
            "column_order": order + [k for k in keys if k not in order],
            "sort": sort,
            "direction": direction,
        }
    except (ValueError, TypeError, KeyError, InvalidOperation):
        raise HTTPException(
            422, "Select valid fields, values and columns for this table."
        ) from None


def own(session, user, key, identifier):
    if not user or not str(identifier).isdigit() or len(str(identifier)) > 18:
        raise HTTPException(404, "View not found.")
    row = session.get(CRMListView, int(identifier))
    if not row or row.user_id != user.id or row.directory != "table:" + key:
        raise HTTPException(404, "View not found.")
    return row


def resolve(request, session, key):
    prefix = "tv_" + key + "_"
    user = getattr(request.state, "portal_user", None)
    identifier = request.query_params.get(prefix + "view")
    row = (
        own(session, user, key, identifier) if identifier not in (None, "all") else None
    )
    if identifier is None and user:
        row = session.scalar(
            select(CRMListView).where(
                CRMListView.user_id == user.id,
                CRMListView.directory == "table:" + key,
                CRMListView.is_default == 1,
            )
        )
    config = (
        dict(row.config)
        if row
        else {"quick_filters": {}, "conditions": [], "sort": "", "direction": "asc"}
    )
    for part in ("rules", "layout"):
        raw = request.query_params.get(prefix + part)
        if raw is not None:
            try:
                if len(raw) > 16000:
                    raise ValueError()
                value = json.loads(raw)
                if part == "rules":
                    config["conditions"] = value
                elif isinstance(value, dict) and set(value) <= {
                    "columns",
                    "column_order",
                }:
                    config.update(value)
                else:
                    raise ValueError()
            except ValueError:
                raise HTTPException(422, "Invalid view settings.") from None
    for part in ("sort", "direction"):
        if prefix + part in request.query_params:
            config[part] = request.query_params[prefix + part]
    return row, config


def serialise(row):
    return {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "is_default": bool(row.is_default),
        "config": row.config,
    }


@router.get("/table-views/{key}", include_in_schema=False)
def views(request: Request, key: str, session: DbSession):
    schema = schema_for(request, key)
    user = getattr(request.state, "portal_user", None)
    row, config = resolve(request, session, key)
    # Scope controls on the current page override saved defaults.
    config["quick_filters"] = dict(config.get("quick_filters", {}))
    for name, value in request.query_params.items():
        if (
            name not in ("schema", "page")
            and not name.startswith("tv_")
            and not (
                key in {"product-batches", "organisation-locations"} and name == "q"
            )
        ):
            config["quick_filters"][name] = value
    if request.query_params.get("tv_" + key + "_q") is not None:
        config["quick_filters"]["q"] = request.query_params["tv_" + key + "_q"]
    config = normalise(config, schema)
    for field in schema:
        field["operators"] = list(
            CRMField(field["key"], field["label"], field["type"]).operators
        )
    saved = (
        list(
            session.scalars(
                select(CRMListView)
                .where(
                    CRMListView.user_id == user.id,
                    CRMListView.directory == "table:" + key,
                )
                .order_by(CRMListView.name)
            )
        )
        if user
        else []
    )
    return {
        "available": bool(user),
        "views": [serialise(r) for r in saved],
        "selected": serialise(row) if row else None,
        "config": config,
        "fields": schema,
        "presets": [],
        "server_filtered": key in SQL_KEYS,
    }


@router.post("/table-views/{key}", include_in_schema=False)
async def save(request: Request, key: str, session: DbSession):
    schema = schema_for(request, key)
    data = await review_form(request)
    try:
        config = normalise(json.loads(data.get("config", "{}")), schema)
    except ValueError:
        raise HTTPException(422, "Invalid view settings.") from None
    command = data.get("command")
    if command == "preview":
        return {"config": config}
    user = getattr(request.state, "portal_user", None)
    if not user:
        raise HTTPException(401, "Sign in to save a view.")
    session.get(PortalUser, user.id, with_for_update=True)
    row = (
        own(session, user, key, data["id"])
        if data.get("id") and command != "create"
        else None
    )
    if row and data.get("version") != str(row.version):
        raise HTTPException(409, "This view changed. Reload before saving.")
    if command == "delete":
        if not row:
            raise HTTPException(404, "View not found.")
        session.delete(row)
    elif command in ("save", "create"):
        name = data.get("name", "").strip()
        if not name or len(name) > 80:
            raise HTTPException(422, "Enter a view name of up to 80 characters.")
        saved = list(
            session.scalars(
                select(CRMListView).where(
                    CRMListView.user_id == user.id,
                    CRMListView.directory == "table:" + key,
                )
            )
        )
        if any(r.name.casefold() == name.casefold() and r != row for r in saved):
            raise HTTPException(409, "You already have a view with this name.")
        if not row and len(saved) >= 100:
            raise HTTPException(422, "Use at most 100 views for one table.")
        if not row:
            row = CRMListView(
                user_id=user.id,
                directory="table:" + key,
                name=name,
                config=config,
                is_default=0,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            session.add(row)
        default = data.get("is_default") == "true"
        if default:
            for other in saved:
                if other != row:
                    other.is_default = 0
        row.name = name
        row.config = config
        row.is_default = int(default)
        row.updated_at = utcnow()
    else:
        raise HTTPException(422, "Invalid view action.")
    try:
        session.commit()
    except (IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(409, "This view changed. Reload before saving.") from None
    return {"view": None if command == "delete" else serialise(row)}


def prepare(request, session, key):
    """Canonicalise saved scope controls before FastAPI re-parses list arguments."""
    row, _ = resolve(request, session, key)
    if row:
        quick = dict(row.config.get("quick_filters", {}))
        if key in {"product-batches", "organisation-locations"} and "q" in quick:
            quick["tv_" + key + "_q"] = quick.pop("q")
        params = quick | dict(request.query_params)
        params["tv_" + key + "_view"] = str(row.id)
        if params != dict(request.query_params):
            raise HTTPException(
                303, headers={"Location": request.url.path + "?" + urlencode(params)}
            )


def apply_sql(request, session, statement, key):
    _, config = resolve(request, session, key)
    expressions = sql_fields(key)
    fields = {
        f"c{i}": {"key": f"c{i}", "label": f"Column {i + 1}", "type": kind}
        for i, (_, kind) in enumerate(expressions)
    }
    schema = list(fields.values())
    # The server validates against its own registry, never client SQL or field names.
    config = normalise({**config, "columns": None, "column_order": None}, schema)
    if key in {"product-batches", "organisation-locations"}:
        search = request.query_params.get(
            "tv_" + key + "_q", config["quick_filters"].get("q", "")
        )
        if search:
            statement = statement.where(
                or_(
                    *(
                        func.lower(cast(column, String)).contains(
                            search.lower(), autoescape=True
                        )
                        for column, _ in expressions
                    )
                )
            )
    for condition in config["conditions"]:
        column, kind = expressions[int(condition["field"][1:])]
        op = condition["operator"]
        value = condition["value"]
        missing = or_(column.is_(None), func.trim(cast(column, String)) == "")
        if op == "empty":
            test = missing
        elif op == "not_empty":
            test = ~missing
        elif op == "contains":
            test = func.lower(cast(column, String)).contains(
                value.lower(), autoescape=True
            )
        elif op in ("less_than", "before"):
            test = column < (Decimal(value) if kind == "number" else value)
        elif op in ("greater_than", "after"):
            test = column > (Decimal(value) if kind == "number" else value)
        else:
            test = (
                column == Decimal(value)
                if kind == "number"
                else func.lower(cast(column, String)) == str(value).lower()
            )
        statement = statement.where(test)
    if config["sort"]:
        column, _ = expressions[int(config["sort"][1:])]
        order = column.desc() if config["direction"] == "desc" else column.asc()
        statement = statement.order_by(None).order_by(
            column.is_(None), order, *statement._order_by_clauses
        )
    return statement
