"""Shared navigation for records opened from a portal list."""

from urllib.parse import urlencode

from sqlalchemy import func, select


def filter_query(request, *keys):
    if request.url.path.startswith("/crm/"):
        keys = tuple(dict.fromkeys((*keys, "view", "rules", "sort", "direction", "layout", "preset")))
    keys = tuple(dict.fromkeys((*keys, *(key for key in request.query_params if key.startswith("tv_")))))
    values = {
        key: request.query_params[key] for key in keys if key in request.query_params
    }
    return f"?{urlencode(values)}" if values else ""


def record_navigation(
    path,
    label,
    previous=None,
    following=None,
    *,
    query="",
    suffix="",
    back_query=None,
    back_path=None,
):
    return {
        "back": (back_path or path) + (query if back_query is None else back_query),
        "label": label,
        "previous": f"{path}/{previous}{suffix}{query}"
        if previous is not None
        else None,
        "next": f"{path}/{following}{suffix}{query}" if following is not None else None,
    }


def ordered_neighbours(session, statement, column, identifier, ordering):
    scope = (
        statement.order_by(None)
        .with_only_columns(
            column.label("record_id"),
            func.lag(column).over(order_by=ordering).label("previous_id"),
            func.lead(column).over(order_by=ordering).label("next_id"),
        )
        .subquery()
    )
    result = session.execute(
        select(scope.c.previous_id, scope.c.next_id).where(
            scope.c.record_id == identifier
        )
    ).first()
    return tuple(result) if result else (None, None)


def list_record_navigation(
    session, statement, column, identifier, ordering, path, label, *, view_request=None, table_key=None, **urls
):
    if view_request is not None and table_key:
        from app.portal.table_views import apply_sql
        statement = apply_sql(view_request, session, statement.order_by(*ordering), table_key)
        ordering = tuple(statement._order_by_clauses)
    return record_navigation(
        path,
        label,
        *ordered_neighbours(session, statement, column, identifier, ordering),
        **urls,
    )
