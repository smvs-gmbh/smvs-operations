from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db.session import get_session
from app.domain.models import Batch, ProductSourceRecord, ProductVersion
from app.portal import queries
from app.portal.record_navigation import filter_query, list_record_navigation

DbSession = Annotated[Session, Depends(get_session)]

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def number(value):
    return "—" if value is None else f"{value:,}".replace(",", "’")


templates.env.filters["number"] = number
templates.env.globals["filter_query"] = filter_query


@router.get("/", include_in_schema=False)
def index():
    return RedirectResponse("/products")


USER_GUIDE = Path(__file__).resolve().parents[2] / "docs/overview/USER-GUIDE.md"
guide_renderer = MarkdownIt("commonmark", {"html": False}).enable("table")


@router.get("/user-guide", include_in_schema=False)
def user_guide(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="user_guide.html",
        context={
            "title": "User Guide",
            "active": "user_guide",
            "guide": guide_renderer.render(USER_GUIDE.read_text(encoding="utf-8")),
        },
    )


@router.get("/products", include_in_schema=False)
def product_list(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    status: str = "",
    version: str = Query("", max_length=100),
    page: int = Query(1, ge=1, le=10000),
):
    if status and status not in queries.STATUS_LABELS:
        raise HTTPException(422, "Unknown matching status.")
    ctx = queries.context(session)
    rows, pagination = (
        queries.products(
            session, ctx["publication"], q=q, status=status, version=version, page=page
        )
        if ctx["publication"]
        else ([], {"page": 1, "pages": 1, "total": 0, "first": 0, "last": 0})
    )
    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            **ctx,
            "active": "products",
            "title": "Products",
            "rows": rows,
            "pagination": pagination,
            "q": q,
            "status": status,
            "version_filter": version,
        },
    )


@router.get("/batches", include_in_schema=False)
def batch_list(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    version: str = Query("", max_length=100),
    state: str = Query("not_expired", max_length=100),
    page: int = Query(1, ge=1, le=10000),
):
    ctx = queries.context(session)
    rows, pagination = (
        queries.batches(
            session, ctx["publication"], q=q, version=version, state=state, page=page
        )
        if ctx["publication"]
        else ([], {"page": 1, "pages": 1, "total": 0, "first": 0, "last": 0})
    )
    return templates.TemplateResponse(
        request=request,
        name="batches.html",
        context={
            **ctx,
            "active": "batches",
            "title": "Batches",
            "rows": rows,
            "pagination": pagination,
            "q": q,
            "version_filter": version,
            "state_filter": state,
            "batch_states": queries.batch_states(session, ctx["publication"])
            if ctx["publication"]
            else [],
        },
    )


def product_navigation(request, session, publication, identifier, *, suffix=""):
    return list_record_navigation(
        session,
        queries.product_statement(
            publication,
            **{
                key: request.query_params.get(key, "")
                for key in ("q", "status", "version")
            },
        ),
        ProductSourceRecord.id,
        identifier,
        queries.PRODUCT_ORDER,
        "/products",
        "Products",
        suffix=suffix,
        query=filter_query(request, "q", "status", "version"),
    )


@router.get("/products/{source_id}", include_in_schema=False)
def product_detail(
    request: Request,
    source_id: int,
    session: DbSession,
    page: int = Query(1, ge=1, le=10000),
):
    ctx = queries.context(session)
    if ctx["publication"] is None:
        raise HTTPException(404, "No published product dataset.")
    row = session.execute(
        queries.base_query(ctx["publication"]).where(
            ProductSourceRecord.id == source_id
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Product not found in the current dataset.")
    product = queries.product_view(row)
    rows, pagination = queries.batches(
        session, ctx["publication"], source_id=source_id, page=page
    )
    versions = session.scalars(
        select(ProductVersion)
        .where(ProductVersion.product_source_id == source_id)
        .order_by(ProductVersion.version_number, ProductVersion.id)
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="product_detail.html",
        context={
            **ctx,
            "active": "products",
            "title": product["name"] or product["gtin14"] or product["source_code"],
            "product": product,
            "record_nav": product_navigation(
                request, session, ctx["publication"], source_id
            ),
            "rows": rows,
            "pagination": pagination,
            "versions": versions,
        },
    )


@router.get("/products/{source_id}/source", include_in_schema=False)
def product_source(request: Request, source_id: int, session: DbSession):
    ctx = queries.context(session)
    if ctx["publication"] is None:
        raise HTTPException(404, "No published product dataset.")
    row = session.execute(
        queries.base_query(ctx["publication"]).where(
            ProductSourceRecord.id == source_id
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Product not found in the current dataset.")
    product = queries.product_view(row)
    return templates.TemplateResponse(
        request=request,
        name="source.html",
        context={
            **ctx,
            **queries.original_values(session, row[0], kind="Products"),
            "active": "products",
            "title": "NMVS Products · Original data",
            "product": product,
            "record_nav": product_navigation(
                request, session, ctx["publication"], source_id, suffix="/source"
            ),
            "back_url": f"/products/{source_id}",
            "back_label": "Swiss product context",
        },
    )


@router.get("/batches/{batch_id}/source", include_in_schema=False)
def batch_source(request: Request, batch_id: int, session: DbSession):
    ctx = queries.context(session)
    if ctx["publication"] is None:
        raise HTTPException(404, "No published product dataset.")
    source = session.get(Batch, batch_id)
    if (
        source is None
        or not source.is_observed
        or source.last_mapping_run_id != ctx["publication"].mapping_run_id
    ):
        raise HTTPException(404, "Batch not found in the current dataset.")
    row = session.execute(
        queries.base_query(ctx["publication"]).where(
            ProductSourceRecord.id == source.product_source_id
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Product not found in the current dataset.")
    product = queries.product_view(row)
    related = request.query_params.get("related") == "true"

    return templates.TemplateResponse(
        request=request,
        name="source.html",
        context={
            **ctx,
            **queries.original_values(session, source, kind="Batches"),
            "active": "batches",
            "title": "NMVS Batches · Original data",
            "product": product,
            "batch_code": source.batch_code,
            "record_nav": list_record_navigation(
                session,
                queries.batch_statement(
                    ctx["publication"],
                    q=request.query_params.get("q", ""),
                    version=request.query_params.get("version", ""),
                    state=""
                    if related
                    else request.query_params.get("state", "not_expired"),
                    source_id=source.product_source_id if related else None,
                ),
                Batch.id,
                batch_id,
                queries.BATCH_ORDER,
                "/batches",
                "Product and related batches" if related else "Batches",
                suffix="/source",
                query=filter_query(request, "q", "version", "state", "related"),
                back_path=f"/products/{product['id']}" if related else None,
                back_query="" if related else None,
            ),
            "back_url": f"/products/{product['id']}",
            "back_label": "Product and related batches",
        },
    )
