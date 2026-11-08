import csv
import io
import re
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import parse_qsl, quote, unquote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.db.models import (
    AcquiredArtifact,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.domain.crm.agreements import (
    AGREEMENT_PDF_SOURCES,
    AGREEMENT_STATUSES,
    MANUAL_SOURCE,
    MAX_PDF_BYTES,
    agreement_candidates,
    archive_pdf,
)
from app.domain.crm.agreements import REPORT_TYPE as AGREEMENT_PDF
from app.domain.crm.company_research import draft_company_summary
from app.domain.crm.contact_assignments import spoc_ids
from app.domain.crm.contacts import MAILBOX_TYPES
from app.domain.crm.declaration_fees import DEFAULT_BASE_FEE, calculate_fees
from app.domain.crm.end_users import (
    contact_reference_index,
    current_organisations,
    match_end_users,
    resolve_end_user_contacts,
)
from app.domain.crm.imports import (
    SOURCE,
    TABLES,
    linked_values,
    relation_profile,
    staged_crm_export,
    staged_crm_metadata,
)
from app.domain.crm.mah_profile import (
    ASSOCIATIONS,
    MAH_MAPPED_COLUMNS,
    MAH_REVIEW_COLUMNS,
    PROFILE_GROUPS,
    association_values,
    logo_url,
    profile_defaults,
)
from app.domain.crm.mahs import CONTRACT_STATUSES
from app.domain.crm.self_declarations import TABLE as DECLARATION_TABLE
from app.domain.models import (
    CRMAgreement,
    CRMAgreementExclusion,
    CRMAgreementMAH,
    CRMContact,
    CRMEndUser,
    CRMMah,
    CRMMahTransfer,
    CRMSelfDeclaration,
    EndUserImportReview,
    LocalOrganisation,
)
from app.integration.artifacts.storage import utcnow
from app.portal.exception_routes import review_form
from app.portal.record_navigation import (
    filter_query,
    record_navigation,
)
from app.portal.routes import DbSession, templates

from app.portal.crm_views import (
    crm_paged, crm_navigation, configured_rows, list_catalogue_context,
    router as views_router,
)
from app.portal.crm_list_preferences import (
    apply_saved_crm_filters,
    router as preferences_router,
)

router = APIRouter(dependencies=[Depends(apply_saved_crm_filters)])
router.include_router(preferences_router)
router.include_router(views_router)

EDIT_SECTIONS = {
    "general": "General",
    "company-summary": "Company summary",
    "address": "Address",
    "invoice": "Invoice information",
    "contacts": "Contacts",
}


def end_user_import_review(session, staged_rows, query, pending_only):
    publication, results = match_end_users(session, staged_rows)
    reviewed = set(
        session.scalars(
            select(EndUserImportReview.staging_row_id).where(
                EndUserImportReview.staging_row_id.in_([row.id for row in staged_rows])
            )
        )
    )
    search = query.strip().casefold()
    visible = [
        result
        for result in results
        if (not pending_only or result[0] not in reviewed)
        and any(
            search in str(value).casefold()
            for value in (
                result[1]["Record Id"],
                result[1]["End User Name"],
                result[1].get("Software Product", ""),
                result[2],
                result[3].source_organisation_id if result[3] else "",
            )
        )
    ]
    return {
        "rows": visible,
        "counts": Counter(status for _, _, status, _ in results),
        "snapshot_date": publication.snapshot_date if publication else None,
        "reviewed": reviewed,
        "end_user_ids": dict(
            session.execute(
                select(CRMEndUser.source_row_id, CRMEndUser.id).where(
                    CRMEndUser.source_row_id.in_([row.id for row in staged_rows])
                )
            ).all()
        ),
        "query": query,
        "pending_only": pending_only,
    }


@router.get("/crm/imports", include_in_schema=False)
def crm_imports(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    pending_only: bool = False,
):
    end_user_review = None
    profiles = {}
    records = {}
    for table in TABLES:
        result = staged_crm_export(session, table)
        if not result:
            continue
        dataset, metadata, received, staged_rows = result
        rows = [row.raw_row_json for row in staged_rows]
        if table == "End Users":
            end_user_review = end_user_import_review(
                session, staged_rows, q, pending_only
            )
        records[table] = rows
        profiles[table] = {
            "filename": metadata.get("filename"),
            "received": received,
            "total": dataset.row_count,
            "columns": [
                (header, sum(bool(row.get(header, "").strip()) for row in rows))
                for header in dataset.source_headers
            ],
        }
    relations = []
    if "MAH" in records and "Contacts" in records:
        contact_labels = Counter(
            row["Record Id"].strip() for row in records["Contacts"]
        )
        mah_labels = Counter(
            row["Record Id"].strip() for row in records["MAH"] if row.get("Record Id")
        )
        relations.extend(
            (
                f"MAH → Contacts · {field}",
                relation_profile(records["MAH"], field, contact_labels),
            )
            for field in ("Alert contacts", "SPOC", "Contacts")
        )
        relations.append(
            (
                "Contacts → MAH · Link MAH",
                relation_profile(records["Contacts"], "Link MAH", mah_labels),
            )
        )
    if "MAH Agreements" in records and "MAH" in records:
        contract_ids = Counter(
            row["Contract ID"].strip() for row in records["MAH Agreements"]
        )
        relations.append(
            (
                "MAH → MAH Agreements · Agreements",
                relation_profile(records["MAH"], "Agreements", contract_ids),
            )
        )
    suppliers = records.get("IT Suppliers")
    if suppliers:
        supplier_labels = Counter(row["Record Id"].strip() for row in suppliers)
        if "Contacts" in records:
            contact_labels = Counter(
                row["Record Id"].strip() for row in records["Contacts"]
            )
            relations.extend(
                (
                    f"IT Suppliers → Contacts · {field}",
                    relation_profile(suppliers, field, contact_labels),
                )
                for field in ("Contacts", "SPOC")
            )
            relations.append(
                (
                    "Contacts → IT Suppliers",
                    relation_profile(
                        records["Contacts"], "Link IT Supplier", supplier_labels
                    ),
                )
            )
        if "End Users" in records:
            relations.append(
                (
                    "End Users → IT Suppliers",
                    relation_profile(
                        records["End Users"],
                        "Enduser Software Supplier",
                        supplier_labels,
                    ),
                )
            )
    return templates.TemplateResponse(
        request=request,
        name="crm_imports.html",
        context={
            "title": "CRM import review",
            "active": "crm",
            "crm_section": True,
            "profiles": profiles,
            "relations": relations,
            "mah_mapped_columns": MAH_MAPPED_COLUMNS,
            "mah_review_columns": MAH_REVIEW_COLUMNS,
            "end_user_review": end_user_review,
        },
    )


@router.post("/crm/imports/end-users/{row_id}/review", include_in_schema=False)
async def review_end_user_import(request: Request, row_id: int, session: DbSession):
    data = await review_form(request)
    row = session.scalar(
        select(StagingRow.id)
        .join(StagingDataset, StagingDataset.id == StagingRow.staging_dataset_id)
        .join(AcquiredArtifact, AcquiredArtifact.id == StagingDataset.artifact_id)
        .join(ProcessingRun, ProcessingRun.id == StagingDataset.processing_run_id)
        .where(
            StagingRow.id == row_id,
            AcquiredArtifact.source_name == SOURCE,
            AcquiredArtifact.report_type == "End Users",
            ProcessingRun.status == "staged",
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "End User import row not found.")
    mark = session.get(EndUserImportReview, row_id)
    if data.get("reviewed") == "yes":
        if mark is None:
            session.add(EndUserImportReview(staging_row_id=row_id))
    elif mark is not None:
        session.delete(mark)
    session.commit()
    filters = urlencode(
        {
            "q": data.get("q", "")[:150],
            "pending_only": "true" if data.get("pending_only") == "true" else "false",
        }
    )
    return RedirectResponse(f"/crm/imports?{filters}#end-user-review", status_code=303)


def crm_imported_at(session, table):
    source = staged_crm_metadata(session, table)
    return source[2] if source else None


def end_user_directory_statement(q, unlinked, archived):
    statement = select(CRMEndUser, LocalOrganisation).outerjoin(
        LocalOrganisation, CRMEndUser.organisation_id == LocalOrganisation.id
    )
    statement = statement.where(
        CRMEndUser.archived_at.is_not(None)
        if archived
        else CRMEndUser.archived_at.is_(None)
    )
    if q.strip():
        statement = statement.where(
            or_(
                CRMEndUser.name.contains(q.strip(), autoescape=True),
                LocalOrganisation.organisation_name.contains(
                    q.strip(), autoescape=True
                ),
                LocalOrganisation.source_organisation_id.contains(
                    q.strip(), autoescape=True
                ),
            )
        )
    if unlinked:
        statement = statement.where(CRMEndUser.organisation_id.is_(None))
    return statement


def end_user_filter_query(q, unlinked, archived=False, *, request=None):
    filters = {}
    if q:
        filters["q"] = q
    if unlinked:
        filters["unlinked"] = "true"
    if archived:
        filters["archived"] = "true"
    if request is not None:
        filters.update(parse_qsl(filter_query(request, "view", "rules", "sort", "direction", "layout", "preset").lstrip("?")))
    return f"?{urlencode(filters)}" if filters else ""


@router.get("/crm/end-users", include_in_schema=False)
def crm_end_users(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    unlinked: bool = False,
    archived: bool = False,
    page: int = Query(1, ge=1),
):
    statement = end_user_directory_statement(q, unlinked, archived)
    rows, pagination = crm_paged(
        session, statement.order_by(CRMEndUser.name, CRMEndUser.id), page, request, "end-users"
    )
    directory_scope = (
        CRMEndUser.archived_at.is_not(None)
        if archived
        else CRMEndUser.archived_at.is_(None)
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_end_users.html",
        context={
            **list_catalogue_context(request, session, "end-users", [user for user, _ in rows]),
            "title": "CRM · End Users",
            "active": "crm",
            "crm_section": True,
            "imported_at": crm_imported_at(session, "End Users"),
            "directory_total": session.scalar(
                select(func.count()).select_from(CRMEndUser).where(directory_scope)
            ),
            "unlinked_total": session.scalar(
                select(func.count())
                .select_from(CRMEndUser)
                .where(directory_scope, CRMEndUser.organisation_id.is_(None))
            ),
            "rows": rows,
            "pagination": pagination,
            "q": q,
            "unlinked": unlinked,
            "archived": archived,
            "detail_query": filter_query(request, "q", "unlinked", "archived"),
        },
    )


END_USER_FIELDS = {
    "software": ("Software Product", "Software product"),
    "supplier": ("Enduser Software Supplier", "IT supplier"),
    "email": ("Email general", "Email"),
    "phone": ("Phone", "Phone"),
}


@router.get("/crm/end-users/new", include_in_schema=False)
def new_crm_end_user(request: Request, session: DbSession):
    return render_end_user(request, session, None, "general")


@router.get("/crm/end-users/{identifier}", include_in_schema=False)
def crm_end_user(
    request: Request,
    identifier: int,
    session: DbSession,
    edit: str = "",
    q: str = Query("", max_length=150),
    unlinked: bool = False,
):
    user = session.get(CRMEndUser, identifier)
    if user is None:
        raise HTTPException(404, "End User not found.")
    return render_end_user(
        request, session, user, edit if not user.archived_at else "", q, unlinked
    )


def render_end_user(request, session, user, edit, q="", unlinked=False):
    row = (
        session.get(StagingRow, user.source_row_id)
        if user and user.source_row_id
        else None
    )
    source = row.raw_row_json if row else {}
    profile = {
        key: source.get(header, "") for key, (header, _) in END_USER_FIELDS.items()
    } | (user.profile or {} if user else {})
    organisation = (
        session.get(LocalOrganisation, user.organisation_id)
        if user and user.organisation_id
        else None
    )
    options = []
    if user and edit in ("organisation", "true"):
        _, current = current_organisations(session)
        occupied = select(CRMEndUser.organisation_id).where(
            CRMEndUser.id != user.id, CRMEndUser.organisation_id.is_not(None)
        )
        options = list(
            session.scalars(
                current.where(LocalOrganisation.id.not_in(occupied)).order_by(
                    LocalOrganisation.organisation_name, LocalOrganisation.id
                )
            )
        )
        if organisation and all(option.id != organisation.id for option in options):
            options.insert(0, organisation)
        edit = "organisation"
    contact_options = []
    ids = set(profile.get("alert_contact_ids", [])) | set(spoc_ids(profile))
    if edit == "contacts" or ids:
        contacts = select(CRMContact).order_by(CRMContact.label, CRMContact.id)
        contacts = contacts.where(
            or_(CRMContact.archived_at.is_(None), CRMContact.id.in_(ids))
            if edit == "contacts"
            else CRMContact.id.in_(ids)
        )
        contact_options = list(session.scalars(contacts))
    pending_contacts = []
    if source.get("SPOC") or source.get("Alert contacts"):
        _, pending_contacts = resolve_end_user_contacts(
            source, contact_reference_index(session)
        )
    navigation_query = filter_query(request, "q", "unlinked", "archived")
    if user and user.archived_at and "archived" not in request.query_params:
        navigation_query += ("&" if navigation_query else "?") + "archived=true"
    navigation = record_navigation("/crm/end-users", "End Users", query=navigation_query)
    if user and not edit:
        navigation = crm_navigation(
            request, session, end_user_directory_statement(q, unlinked, bool(user.archived_at)),
            CRMEndUser.id, user.id, (CRMEndUser.name, CRMEndUser.id),
            "/crm/end-users", "End Users", query=navigation_query,
        )
    return templates.TemplateResponse(
        request=request,
        name="crm_end_user_detail.html",
        context={
            "title": user.name if user else "New End User",
            "active": "crm",
            "crm_section": True,
            "user": user,
            "record_nav": navigation,
            "detail_query": navigation_query,
            "source": source,
            "profile": profile,
            "spoc_ids": spoc_ids(profile),
            "profile_fields": END_USER_FIELDS,
            "organisation": organisation,
            "edit": edit,
            "options": options,
            "contact_options": contact_options,
            "pending_contact_references": pending_contacts,
            "assigned_contacts": {
                contact.id: contact for contact in contact_options if contact.id in ids
            },
        },
    )


def end_user_fields(data):
    name = data.get("name", "").strip()
    profile = {key: data.get(key, "").strip() for key in END_USER_FIELDS}
    if (
        not name
        or len(name) > 255
        or any(len(value) > 255 for value in profile.values())
    ):
        raise HTTPException(422, "Enter a name and valid End User details.")
    return name, profile


@router.post("/crm/end-users", include_in_schema=False)
async def create_end_user(request: Request, session: DbSession):
    name, profile = end_user_fields(await review_form(request))
    user = CRMEndUser(name=name, profile=profile)
    session.add(user)
    session.commit()
    return RedirectResponse(f"/crm/end-users/{user.id}", status_code=303)


@router.post("/crm/end-users/{identifier}", include_in_schema=False)
async def update_end_user(
    request: Request,
    identifier: int,
    session: DbSession,
    q: str = Query("", max_length=150),
    unlinked: bool = False,
):
    data = await review_form(request)
    user = session.get(CRMEndUser, identifier, with_for_update=True)
    if user is None:
        raise HTTPException(404, "End User not found.")
    if data.get("version") != str(user.version):
        raise HTTPException(409, "This End User changed. Reload before saving.")
    command = data.get("command")
    if command == "restore" and user.archived_at:
        user.archived_at = None
    elif user.archived_at:
        raise HTTPException(409, "Restore this End User before making changes.")
    elif command == "archive":
        user.archived_at = utcnow()
    elif command == "general":
        user.name, profile = end_user_fields(data)
        user.profile = (user.profile or {}) | profile
    elif command == "contacts":
        user.profile = contact_assignments(data, session, user.profile)
    else:
        raise HTTPException(422, "Select a valid End User action.")
    session.commit()
    destination = (
        f"/crm/end-users{end_user_filter_query(q, unlinked, archived=True, request=request)}"
        if command == "archive"
        else f"/crm/end-users/{user.id}{end_user_filter_query(q, unlinked, request=request)}"
    )
    return RedirectResponse(destination, status_code=303)


@router.post("/crm/end-users/{identifier}/organisation", include_in_schema=False)
async def update_end_user_organisation(
    request: Request,
    identifier: int,
    session: DbSession,
    q: str = Query("", max_length=150),
    unlinked: bool = False,
):
    data = await review_form(request)
    user = session.get(CRMEndUser, identifier, with_for_update=True)
    if user is None:
        raise HTTPException(404, "End User not found.")
    if user.archived_at:
        raise HTTPException(
            409, "Restore this End User before changing its organisation."
        )
    current_id = str(user.organisation_id or "")
    if data.get("previous_organisation_id") != current_id:
        raise HTTPException(409, "The organisation link changed. Reload before saving.")
    selected = data.get("organisation_id")
    if selected is None or (
        selected
        and (not selected.isascii() or not selected.isdecimal() or len(selected) > 10)
    ):
        raise HTTPException(422, "Select a valid NMVS organisation.")
    if selected != current_id:
        organisation_id = int(selected) if selected else None
        if organisation_id is not None:
            _, current = current_organisations(session)
            if (
                session.scalar(current.where(LocalOrganisation.id == organisation_id))
                is None
            ):
                raise HTTPException(
                    422, "Select an organisation from the current NMVS snapshot."
                )
            if (
                session.scalar(
                    select(CRMEndUser.id).where(
                        CRMEndUser.organisation_id == organisation_id,
                        CRMEndUser.id != user.id,
                    )
                )
                is not None
            ):
                raise HTTPException(
                    409, "This organisation is already linked to an End User."
                )
        user.organisation_id = organisation_id
        user.link_origin = "manual" if organisation_id else None
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                409, "This organisation is already linked to an End User."
            ) from None
    return RedirectResponse(
        f"/crm/end-users/{identifier}{end_user_filter_query(q, unlinked, request=request)}#organisation",
        status_code=303,
    )


def filtered_suppliers(suppliers, q):
    query = q.strip().casefold()
    rows = [
        row
        for row in suppliers
        if any(
            query in row.raw_row_json.get(field, "").casefold()
            for field in (
                "IT Supplier Name",
                "Record Id",
                "End User Software",
                "Status",
            )
        )
    ]
    rows.sort(key=lambda row: (row.raw_row_json["IT Supplier Name"].casefold(), row.id))
    return rows


@router.get("/crm/it-suppliers", include_in_schema=False)
def crm_it_suppliers(
    request: Request, session: DbSession, q: str = Query("", max_length=150)
):
    export = staged_crm_export(session, "IT Suppliers")
    rows = configured_rows(request, session, "it-suppliers", filtered_suppliers(export[3] if export else [], q))
    return templates.TemplateResponse(
        request=request,
        name="crm_it_suppliers.html",
        context={
            **list_catalogue_context(request, session, "it-suppliers", rows),
            "title": "CRM · IT Suppliers",
            "active": "crm",
            "crm_section": True,
            "imported_at": export[2] if export else None,
            "directory_total": export[0].row_count if export else 0,
            "qualified_total": sum(
                row.raw_row_json.get("Qualified") == "checked" for row in export[3]
            )
            if export
            else 0,
            "rows": rows,
            "q": q,
        },
    )


def supplier_contact_links(session, suppliers):
    """Resolve both Airtable directions using unambiguous exact references."""
    suppliers_by_label = defaultdict(list)
    for row in suppliers:
        suppliers_by_label[row.raw_row_json["Record Id"].strip()].append(row.id)

    contacts_by_label = defaultdict(list)
    links = defaultdict(dict)
    pending_suppliers = defaultdict(set)
    pending_contacts = defaultdict(set)
    for contact, raw in session.execute(
        select(CRMContact, StagingRow.raw_row_json).outerjoin(
            StagingRow, CRMContact.source_row_id == StagingRow.id
        )
    ):
        raw = raw or {}
        contacts_by_label[raw.get("Record Id", contact.label).strip()].append(contact)
        for label in linked_values(raw.get("Link IT Supplier", "")):
            matches = suppliers_by_label[label]
            if len(matches) == 1:
                links[matches[0]][contact.id] = (contact, False)
            else:
                pending_contacts[contact.id].add(label)

    for row in suppliers:
        for field in ("Contacts", "SPOC"):
            for label in linked_values(row.raw_row_json.get(field, "")):
                candidates = contacts_by_label[label]
                if len(candidates) != 1:
                    pending_suppliers[row.id].add(label)
                    continue
                contact = candidates[0]
                links[row.id][contact.id] = (contact, field == "SPOC")
    return links, pending_suppliers, pending_contacts


@router.get("/crm/it-suppliers/{identifier}", include_in_schema=False)
def crm_it_supplier(request: Request, identifier: int, session: DbSession):
    export = staged_crm_export(session, "IT Suppliers")
    supplier = (
        next((row.raw_row_json for row in export[3] if row.id == identifier), None)
        if export
        else None
    )
    if supplier is None:
        raise HTTPException(404, "IT supplier not found.")
    links, pending, _ = supplier_contact_links(session, export[3])
    ids = [
        row.id
        for row in configured_rows(request, session, "it-suppliers", filtered_suppliers(export[3], request.query_params.get("q", "")))
    ]
    position = ids.index(identifier) if identifier in ids else None
    navigation = record_navigation(
        "/crm/it-suppliers",
        "IT Suppliers",
        ids[position - 1] if position is not None and position > 0 else None,
        ids[position + 1] if position is not None and position + 1 < len(ids) else None,
        query=filter_query(request, "q"),
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_it_supplier_detail.html",
        context={
            "title": supplier["IT Supplier Name"],
            "active": "crm",
            "crm_section": True,
            "supplier": supplier,
            "record_nav": navigation,
            "supplier_contacts": sorted(
                links[identifier].values(),
                key=lambda item: item[0].display_name.casefold(),
            ),
            "pending_contacts": sorted(pending[identifier]),
            "software": linked_values(supplier.get("End User Software", "")),
        },
    )


def contact_directory_statement(q, archived=False):
    statement = select(CRMContact).where(
        CRMContact.archived_at.is_not(None)
        if archived
        else CRMContact.archived_at.is_(None)
    )
    if q.strip():
        statement = statement.where(
            or_(
                CRMContact.label.contains(q.strip(), autoescape=True),
                CRMContact.function.contains(q.strip(), autoescape=True),
                CRMContact.profile["first_name"]
                .as_string()
                .contains(q.strip(), autoescape=True),
                CRMContact.profile["last_name"]
                .as_string()
                .contains(q.strip(), autoescape=True),
                CRMContact.profile["email"]
                .as_string()
                .contains(q.strip(), autoescape=True),
            )
        )
    return statement


@router.get("/crm/contacts", include_in_schema=False)
def crm_contacts(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    archived: bool = False,
    page: int = Query(1, ge=1),
):
    statement = contact_directory_statement(q, archived)
    rows, pagination = crm_paged(
        session, statement.order_by(CRMContact.label, CRMContact.id), page, request, "contacts"
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_contacts.html",
        context={
            **list_catalogue_context(request, session, "contacts", [contact for (contact,) in rows]),
            "title": "CRM · Contacts",
            "active": "crm",
            "crm_section": True,
            "imported_at": crm_imported_at(session, "Contacts"),
            "directory_total": session.scalar(
                select(func.count()).select_from(
                    contact_directory_statement("", archived).subquery()
                )
            ),
            "rows": [contact for (contact,) in rows],
            "q": q,
            "archived": archived,
            "pagination": pagination,
        },
    )


ADDRESS_TYPES = {"work": "Work", "personal": "Personal", "other": "Other"}
CONTACT_SECTIONS = {"general", "communication"}
EMAIL = re.compile(r"[^\s@]+@[^\s@]+")


def contact_functions(session):
    values = set(session.scalars(select(CRMContact.function).distinct()))
    values.update(
        raw.get("Function", "")
        for raw in session.scalars(
            select(StagingRow.raw_row_json).join(
                CRMContact,
                CRMContact.source_row_id == StagingRow.id,
            )
        )
    )
    return sorted(
        {role for value in values for role in linked_values(value or "")},
        key=str.casefold,
    )


def contact_organisations(session, contact):
    source = (
        session.get(StagingRow, contact.source_row_id)
        if contact.source_row_id
        else None
    )
    references = (
        linked_values(source.raw_row_json.get("Link MAH", "")) if source else []
    )
    matches = {}
    assigned = {}
    for mah, raw in session.execute(
        select(CRMMah, StagingRow.raw_row_json)
        .outerjoin(StagingRow, CRMMah.source_row_id == StagingRow.id)
        .order_by(CRMMah.name, CRMMah.id)
    ):
        label = (raw or {}).get("Record Id", "").strip()
        if label in references:
            matches.setdefault(label, []).append(mah)
        profile = mah.profile or {}
        if contact.id in spoc_ids(profile) or contact.id in profile.get(
            "alert_contact_ids", []
        ):
            assigned[mah.id] = (mah, "Contact assignment")
    for label, candidates in matches.items():
        if len(candidates) == 1:
            mah = candidates[0]
            assigned.setdefault(mah.id, (mah, "Airtable organisation link"))
    pending = [label for label in references if len(matches.get(label, [])) != 1]
    return sorted(assigned.values(), key=lambda row: row[0].name.casefold()), pending


@router.get("/crm/contacts/{identifier}", include_in_schema=False)
def crm_contact_detail(
    request: Request, identifier: int, session: DbSession, edit: str = ""
):
    contact = session.get(CRMContact, identifier)
    if contact is None:
        raise HTTPException(404, "Contact not found.")
    if contact.archived_at:
        edit = ""
    query = filter_query(request, "q")
    if contact.archived_at:
        query += ("&" if query else "?") + "archived=true"
    profile = {"email": contact.label if EMAIL.fullmatch(contact.label) else ""} | (
        contact.profile or {}
    )
    organisations, pending = contact_organisations(session, contact)
    end_users = [
        user
        for user in session.scalars(
            select(CRMEndUser)
            .where(CRMEndUser.archived_at.is_(None))
            .order_by(CRMEndUser.name)
        )
        if contact.id in spoc_ids(user.profile)
        or contact.id in (user.profile or {}).get("alert_contact_ids", [])
    ]
    export = staged_crm_export(session, "IT Suppliers")
    suppliers = export[3] if export else []
    links, _, pending_suppliers = supplier_contact_links(session, suppliers)
    navigation = (
        crm_navigation(
            request, session,
            contact_directory_statement(
                request.query_params.get("q", ""), bool(contact.archived_at)
            ),
            CRMContact.id,
            identifier,
            (CRMContact.label, CRMContact.id),
            "/crm/contacts",
            "Contacts",
            query=query,
        )
        if edit not in CONTACT_SECTIONS
        else record_navigation("/crm/contacts", "Contacts", query=query)
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_contact_detail.html",
        context={
            "title": contact.display_name,
            "active": "crm",
            "crm_section": True,
            "contact": contact,
            "record_nav": navigation,
            "profile": profile,
            "roles": linked_values(contact.function or ""),
            "function_options": contact_functions(session) if edit == "general" else [],
            "address_types": ADDRESS_TYPES,
            "mailbox_types": MAILBOX_TYPES,
            "edit": edit if edit in CONTACT_SECTIONS else "",
            "organisations": organisations,
            "end_users": end_users,
            "suppliers": [
                (row, links[row.id][contact.id][1])
                for row in suppliers
                if contact.id in links[row.id]
            ],
            "pending_suppliers": sorted(pending_suppliers[contact.id]),
            "pending": pending,
        },
    )


@router.post("/crm/contacts/{identifier}", include_in_schema=False)
async def update_crm_contact(request: Request, identifier: int, session: DbSession):
    data = await review_form(request)
    contact = session.get(CRMContact, identifier, with_for_update=True)
    if contact is None:
        raise HTTPException(404, "Contact not found.")
    if data.get("version") != str(contact.version):
        raise HTTPException(409, "This contact changed. Reload before saving.")
    command = data.get("command")
    if command == "archive" and not contact.archived_at:
        contact.archived_at = utcnow()
    elif command == "restore" and contact.archived_at:
        contact.archived_at = None
    elif command or contact.archived_at:
        raise HTTPException(
            409, "This action is unavailable for the current contact state."
        )
    if command:
        session.commit()
        suffix = "?archived=true" if contact.archived_at else ""
        return RedirectResponse(f"/crm/contacts/{identifier}{suffix}", status_code=303)
    section = data.get("section")
    if section == "general":
        fields = {
            key: data.get(key, "").strip()
            for key in ("first_name", "last_name", "address_type")
        }
        roles = [
            key.removeprefix("function:")
            for key, value in data.items()
            if key.startswith("function:") and value == "yes"
        ]
        if (
            fields["address_type"]
            and fields["address_type"] not in ADDRESS_TYPES
            or any(len(fields[key]) > 150 for key in ("first_name", "last_name"))
            or not set(roles).issubset(contact_functions(session))
        ):
            raise HTTPException(422, "Enter valid general contact details.")
        buffer = io.StringIO()
        csv.writer(buffer).writerow(roles)
        contact.function = buffer.getvalue().rstrip("\r\n") or None
    elif section == "communication":
        fields = {key: data.get(key, "").strip() for key in ("email", "phone")}
        if (
            fields["email"]
            and not EMAIL.fullmatch(fields["email"])
            or len(fields["email"]) > 254
            or len(fields["phone"]) > 100
        ):
            raise HTTPException(422, "Enter valid contact details.")
        if "mailbox_type" in data:
            mailbox_type = data["mailbox_type"]
            if mailbox_type and mailbox_type not in MAILBOX_TYPES:
                raise HTTPException(422, "Select a valid mailbox type.")
            fields["mailbox_type"] = mailbox_type
    else:
        raise HTTPException(422, "Select a valid contact section.")
    contact.profile = (contact.profile or {}) | fields
    try:
        session.commit()
    except StaleDataError:
        session.rollback()
        raise HTTPException(
            409, "This contact changed. Reload before saving."
        ) from None
    return RedirectResponse(
        f"/crm/contacts/{identifier}{filter_query(request, 'q')}#{section}",
        status_code=303,
    )


AGREEMENTS_PATH = "/crm/agreements"
AGREEMENT_FILTERS = ("q", "status", "link", "attachments")


def agreement_documents():
    return (
        select(
            AcquiredArtifact.id,
            AcquiredArtifact.report_metadata,
            CRMAgreementExclusion.artifact_id.is_not(None).label("excluded"),
        )
        .outerjoin(
            CRMAgreementExclusion,
            CRMAgreementExclusion.artifact_id == AcquiredArtifact.id,
        )
        .where(
            AcquiredArtifact.source_name.in_(AGREEMENT_PDF_SOURCES),
            AcquiredArtifact.report_type == AGREEMENT_PDF,
        )
    )


def agreement_directory(session, params):
    q = params.get("q", "").strip()[:150]
    status, link, attachments = (params.get(key, "") for key in AGREEMENT_FILTERS[1:])
    statement = select(CRMAgreement)
    if q:
        statement = statement.where(
            or_(
                CRMAgreement.contract_id.contains(q, autoescape=True),
                CRMAgreement.contractor.contains(q, autoescape=True),
                CRMAgreement.mahs.any(CRMMah.name.contains(q, autoescape=True)),
            )
        )
    if status:
        statement = statement.where(CRMAgreement.status == status)
    candidates = agreement_candidates(session)
    ambiguous = [
        contract for contract, matches in candidates.items() if len(matches) > 1
    ]
    if link == "linked":
        statement = statement.where(CRMAgreement.mahs.any())
    elif link in ("unlinked", "ambiguous"):
        statement = statement.where(~CRMAgreement.mahs.any())
        if link == "ambiguous":
            statement = statement.where(CRMAgreement.contract_id.in_(ambiguous))

    counts = Counter(
        metadata["contract_id"]
        for _, metadata, _ in session.execute(
            agreement_documents().where(CRMAgreementExclusion.artifact_id.is_(None))
        )
    )
    if attachments == "missing":
        statement = statement.where(CRMAgreement.contract_id.not_in(counts))
    elif attachments == "multiple":
        statement = statement.where(
            CRMAgreement.contract_id.in_(
                [key for key, count in counts.items() if count > 1]
            )
        )
    return statement, candidates, counts


@router.get(AGREEMENTS_PATH, include_in_schema=False)
def crm_agreements(request: Request, session: DbSession, page: int = Query(1, ge=1)):
    statement, candidates, counts = agreement_directory(session, request.query_params)
    rows, pagination = crm_paged(
        session,
        statement.options(selectinload(CRMAgreement.mahs)).order_by(
            CRMAgreement.contract_id
        ),
        page, request, "agreements", pdf_counts=counts,
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_agreements.html",
        context={
            **list_catalogue_context(request, session, "agreements", [agreement for (agreement,) in rows], pdf_counts=counts),
            "title": "CRM · MAH Agreements",
            "active": "crm",
            "crm_section": True,
            "rows": rows,
            "candidates": candidates,
            "counts": counts,
            "pagination": pagination,
            "filters": request.query_params,
            "statuses": list(
                session.scalars(
                    select(CRMAgreement.status).distinct().order_by(CRMAgreement.status)
                )
            ),
            "total": session.scalar(select(func.count()).select_from(CRMAgreement)),
            "unlinked": session.scalar(
                select(func.count())
                .select_from(CRMAgreement)
                .where(~CRMAgreement.mahs.any())
            ),
            "imported_at": crm_imported_at(session, "MAH Agreements"),
        },
    )


@router.get(AGREEMENTS_PATH + "/new", include_in_schema=False)
def new_crm_agreement(request: Request, session: DbSession, mah_id: int | None = None):
    mahs = list(
        session.scalars(
            select(CRMMah)
            .where(CRMMah.archived_at.is_(None))
            .order_by(CRMMah.name, CRMMah.id)
        )
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_agreement_new.html",
        context={
            "title": "New agreement",
            "active": "crm",
            "crm_section": True,
            "mahs": mahs,
            "selected_mah": mah_id,
            "agreement_statuses": AGREEMENT_STATUSES,
        },
    )


@router.post(AGREEMENTS_PATH, include_in_schema=False)
async def create_crm_agreement(request: Request, session: DbSession):
    data = await review_form(request)
    contract_id = data.get("contract_id", "").strip()
    contractor = data.get("contractor", "").strip()
    if not contract_id or len(contract_id) > 100 or len(contractor) > 255:
        raise HTTPException(422, "Enter a contract ID and a valid contractor name.")
    value = data.get("mah_id", "")
    mah = None
    if value:
        if not re.fullmatch(r"[0-9]{1,10}", value):
            raise HTTPException(422, "Choose a valid MAH.")
        mah = session.get(CRMMah, int(value))
        if not mah or mah.archived_at:
            raise HTTPException(422, "Choose an active MAH.")
    if not contractor and not mah:
        raise HTTPException(422, "Enter a contractor or select a MAH.")
    agreement = CRMAgreement(
        contract_id=contract_id,
        contractor=contractor or mah.name,
        mahs=[mah] if mah else [],
    )
    update_agreement_details(agreement, data)
    session.add(agreement)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.scalar(
            select(CRMAgreement.id).where(CRMAgreement.contract_id == contract_id)
        ):
            raise HTTPException(409, "This contract ID already exists.") from None
        raise
    return RedirectResponse(f"{AGREEMENTS_PATH}/{agreement.id}", status_code=303)


def agreement_or_404(session, identifier, *, lock=False):
    agreement = session.get(CRMAgreement, identifier, with_for_update=lock)
    if agreement is None:
        raise HTTPException(404, "Agreement not found.")
    return agreement


@router.get(AGREEMENTS_PATH + "/{identifier}", include_in_schema=False)
def crm_agreement(request: Request, identifier: int, session: DbSession):
    agreement = agreement_or_404(session, identifier)
    source = (
        session.get(StagingRow, agreement.source_row_id)
        if agreement.source_row_id
        else None
    )
    statement, candidates, counts = agreement_directory(session, request.query_params)
    navigation = crm_navigation(
        request, session,
        statement,
        CRMAgreement.id,
        identifier,
        (CRMAgreement.contract_id,),
        AGREEMENTS_PATH,
        "MAH Agreements",
        query=filter_query(request, *AGREEMENT_FILTERS), pdf_counts=counts,
    )
    documents = session.execute(
        agreement_documents()
        .where(
            AcquiredArtifact.report_metadata["contract_id"].as_string()
            == agreement.contract_id
        )
        .order_by(AcquiredArtifact.id)
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="crm_agreement_detail.html",
        context={
            "title": agreement.contract_id,
            "active": "crm",
            "crm_section": True,
            "agreement": agreement,
            "agreement_statuses": tuple(
                dict.fromkeys((*AGREEMENT_STATUSES, agreement.status))
            ),
            "record_nav": navigation,
            "documents": documents,
            "source": source.raw_row_json if source else {},
            "candidates": candidates[agreement.contract_id],
            "assigned_mah_ids": {mah.id for mah in agreement.mahs},
            "mahs": list(
                session.scalars(
                    select(CRMMah)
                    .where(
                        or_(
                            CRMMah.archived_at.is_(None),
                            CRMMah.id.in_([mah.id for mah in agreement.mahs]),
                        )
                    )
                    .order_by(CRMMah.name, CRMMah.id)
                )
            ),
        },
    )


def update_agreement_details(agreement, data):
    status = data.get("status", "")
    if status not in AGREEMENT_STATUSES and status != agreement.status:
        raise HTTPException(422, "Choose a valid agreement status.")
    try:
        value = data.get("signing_date", "")
        signing_date = date.fromisoformat(value) if value else None
    except ValueError:
        raise HTTPException(422, "Enter a valid signing date.") from None
    agreement.status = status
    agreement.signing_date = signing_date


def selected_ids(data, prefix):
    identifiers = set()
    for key in data:
        if key.startswith(prefix):
            value = key.removeprefix(prefix)
            if not re.fullmatch(r"[0-9]{1,10}", value):
                raise HTTPException(422, "Invalid assignment.")
            identifiers.add(int(value))
    return identifiers


@router.post(AGREEMENTS_PATH + "/{identifier}", include_in_schema=False)
async def update_crm_agreement(request: Request, identifier: int, session: DbSession):
    data = await review_form(request)
    agreement = agreement_or_404(session, identifier, lock=True)
    command = data.get("command")
    if command == "details":
        update_agreement_details(agreement, data)
    elif command == "assign":
        if "mah_id" in data:
            # Accept the previous single-selection form from an already open tab.
            value = data["mah_id"]
            identifiers = selected_ids({f"mah:{value}": "yes"} if value else {}, "mah:")
        else:
            identifiers = selected_ids(data, "mah:")
        existing = {mah.id for mah in agreement.mahs}
        mahs = list(session.scalars(select(CRMMah).where(CRMMah.id.in_(identifiers))))
        if len(mahs) != len(identifiers) or any(
            mah.archived_at and mah.id not in existing for mah in mahs
        ):
            raise HTTPException(422, "Choose valid MAHs.")
        agreement.mahs = mahs
    elif command in ("exclude", "restore"):
        value = data.get("artifact_id", "")
        if not re.fullmatch(r"[0-9]{1,10}", value):
            raise HTTPException(422, "Choose a valid attachment.")
        artifact_id = int(value)
        if not session.execute(
            agreement_documents().where(
                AcquiredArtifact.id == artifact_id,
                AcquiredArtifact.report_metadata["contract_id"].as_string()
                == agreement.contract_id,
            )
        ).first():
            raise HTTPException(404, "Attachment not found.")
        exclusion = session.get(CRMAgreementExclusion, artifact_id)
        if command == "exclude" and exclusion is None:
            session.add(CRMAgreementExclusion(artifact_id=artifact_id))
        elif command == "restore" and exclusion is not None:
            session.delete(exclusion)
    else:
        raise HTTPException(422, "Choose a valid agreement action.")
    session.commit()
    return RedirectResponse(
        f"{AGREEMENTS_PATH}/{identifier}{filter_query(request, *AGREEMENT_FILTERS)}",
        status_code=303,
    )


@router.post(AGREEMENTS_PATH + "/{identifier}/pdf", include_in_schema=False)
async def upload_agreement_pdf(request: Request, identifier: int, session: DbSession):
    if not getattr(request.state, "portal_user", None):
        raise HTTPException(403, "Sign in to upload agreement PDFs.")
    if request.headers.get("origin") != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Use the agreement page to upload a PDF.")
    filename = unquote(request.headers.get("x-filename", "")).strip()
    if (
        not filename.lower().endswith(".pdf")
        or len(filename) > 255
        or any(ord(char) < 32 or char in "/\\" for char in filename)
    ):
        raise HTTPException(422, "Choose a PDF with a valid filename.")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_PDF_BYTES:
            raise HTTPException(413, "The PDF exceeds the 12 MiB size limit.")
        content.extend(chunk)
    if not content.startswith(b"%PDF-"):
        raise HTTPException(422, "The file is not a PDF.")
    agreement = agreement_or_404(session, identifier, lock=True)
    archive_pdf(
        session, agreement.contract_id, filename, bytes(content), source=MANUAL_SOURCE
    )
    session.commit()
    return Response(status_code=204)


@router.get(
    AGREEMENTS_PATH + "/{identifier}/pdf/{artifact_id}", include_in_schema=False
)
def agreement_pdf(
    request: Request, identifier: int, artifact_id: int, session: DbSession
):
    if not getattr(request.state, "portal_user", None):
        raise HTTPException(403, "Sign in to download agreement PDFs.")
    agreement = agreement_or_404(session, identifier)
    artifact = session.scalar(
        select(AcquiredArtifact).where(
            AcquiredArtifact.id == artifact_id,
            AcquiredArtifact.source_name.in_(AGREEMENT_PDF_SOURCES),
            AcquiredArtifact.report_type == AGREEMENT_PDF,
            AcquiredArtifact.report_metadata["contract_id"].as_string()
            == agreement.contract_id,
        )
    )
    if artifact is None:
        raise HTTPException(404, "Attachment not found.")
    filename = quote(artifact.report_metadata["filename"], safe="")
    return Response(
        artifact.artifact_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


DECLARATIONS_PATH = "/crm/self-declarations"
DECLARATION_FILTERS = ("q", "year", "assignment", "duplicates", "mah_id")
DECLARATION_ORDER = (
    CRMSelfDeclaration.declaration_year.desc(),
    CRMSelfDeclaration.record_label,
    CRMSelfDeclaration.id,
)


def declaration_duplicates():
    return (
        select(CRMSelfDeclaration.record_label)
        .group_by(CRMSelfDeclaration.record_label)
        .having(func.count() > 1)
    )


def declaration_directory(q, year, assignment, duplicates, mah_id):
    statement = select(CRMSelfDeclaration, CRMMah.name).outerjoin(
        CRMMah, CRMSelfDeclaration.mah_id == CRMMah.id
    )
    if q.strip():
        text = q.strip()
        statement = statement.where(
            or_(
                CRMSelfDeclaration.record_label.contains(text, autoescape=True),
                CRMSelfDeclaration.source_mah_name.contains(text, autoescape=True),
                CRMMah.name.contains(text, autoescape=True),
            )
        )
    if year:
        statement = statement.where(CRMSelfDeclaration.declaration_year == int(year))
    if mah_id is not None:
        statement = statement.where(CRMSelfDeclaration.mah_id == mah_id)
    if assignment == "unassigned":
        statement = statement.where(CRMSelfDeclaration.mah_id.is_(None))
    elif assignment == "linked":
        statement = statement.where(CRMSelfDeclaration.mah_id.is_not(None))
    if duplicates:
        statement = statement.where(
            CRMSelfDeclaration.record_label.in_(declaration_duplicates())
        )
    return statement


@router.get(DECLARATIONS_PATH, include_in_schema=False)
def crm_self_declarations(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    year: str = Query("", pattern=r"^(?:[0-9]{4})?$"),
    assignment: Literal["", "linked", "unassigned"] = "",
    duplicates: bool = False,
    mah_id: int | None = None,
    page: int = Query(1, ge=1),
):
    statement = declaration_directory(q, year, assignment, duplicates, mah_id)
    rows, pagination = crm_paged(session, statement.order_by(*DECLARATION_ORDER), page, request, "self-declarations")
    return templates.TemplateResponse(
        request=request,
        name="crm_self_declarations.html",
        context={
            **list_catalogue_context(request, session, "self-declarations", [item for item, _ in rows]),
            "title": "Self-declarations",
            "active": "crm",
            "crm_section": True,
            "rows": rows,
            "pagination": pagination,
            "q": q,
            "year": year,
            "assignment": assignment,
            "duplicates": duplicates,
            "mah": session.get(CRMMah, mah_id) if mah_id is not None else None,
            "years": list(
                session.scalars(
                    select(CRMSelfDeclaration.declaration_year)
                    .distinct()
                    .order_by(CRMSelfDeclaration.declaration_year.desc())
                )
            ),
            "duplicate_labels": set(session.scalars(declaration_duplicates())),
            "total": session.scalar(
                select(func.count()).select_from(CRMSelfDeclaration)
            ),
            "unassigned": session.scalar(
                select(func.count())
                .select_from(CRMSelfDeclaration)
                .where(CRMSelfDeclaration.mah_id.is_(None))
            ),
            "imported_at": crm_imported_at(session, DECLARATION_TABLE),
        },
    )


@router.get(DECLARATIONS_PATH + "/{identifier}", include_in_schema=False)
def crm_self_declaration(
    request: Request,
    identifier: int,
    session: DbSession,
    q: str = Query("", max_length=150),
    year: str = Query("", pattern=r"^(?:[0-9]{4})?$"),
    assignment: Literal["", "linked", "unassigned"] = "",
    duplicates: bool = False,
    mah_id: int | None = None,
):
    declaration = session.get(CRMSelfDeclaration, identifier)
    if declaration is None:
        raise HTTPException(404, "Self-declaration not found.")
    row = (
        session.get(StagingRow, declaration.source_row_id)
        if declaration.source_row_id
        else None
    )
    source = row.raw_row_json if row else {}
    base_value = (source.get("Base fee amount") or "").strip()
    preview = None
    try:
        preview = calculate_fees(
            declaration.packs_sold,
            (source.get("RX sales group") or "").strip(),
            Decimal(base_value.replace(",", ".")) if base_value else DEFAULT_BASE_FEE,
        )
    except (ValueError, InvalidOperation):
        pass
    navigation = crm_navigation(
        request, session,
        declaration_directory(q, year, assignment, duplicates, mah_id),
        CRMSelfDeclaration.id,
        identifier,
        DECLARATION_ORDER,
        DECLARATIONS_PATH,
        "Self-declarations",
        query=filter_query(request, *DECLARATION_FILTERS),
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_self_declaration_detail.html",
        context={
            "title": declaration.record_label,
            "active": "crm",
            "crm_section": True,
            "declaration": declaration,
            "source": source,
            "fee_preview": preview,
            "uses_default_base_fee": not base_value,
            "mah": session.get(CRMMah, declaration.mah_id)
            if declaration.mah_id
            else None,
            "record_nav": navigation,
        },
    )


def mah_directory_statement(q, archived, agreement=""):
    statement = select(CRMMah).where(
        CRMMah.archived_at.is_not(None) if archived else CRMMah.archived_at.is_(None)
    )
    if q.strip():
        text = q.strip()
        statement = statement.where(
            or_(
                CRMMah.name.contains(text, autoescape=True),
                CRMMah.gln.contains(text, autoescape=True),
            )
        )
    linked = (
        select(CRMAgreement.id)
        .join(CRMAgreementMAH)
        .where(CRMAgreementMAH.mah_id == CRMMah.id)
    )
    if agreement == "linked":
        statement = statement.where(linked.exists())
    elif agreement == "missing":
        statement = statement.where(~linked.exists())
    elif agreement == "no-signed":
        statement = statement.where(
            ~linked.where(CRMAgreement.status == "Signed").exists()
        )
    return statement


@router.get("/crm/mahs", include_in_schema=False)
def crm_mahs(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    archived: bool = False,
    agreement: Literal["", "linked", "missing", "no-signed"] = "",
    page: int = Query(1, ge=1),
):
    statement = mah_directory_statement(q, archived, agreement)
    rows, pagination = crm_paged(session, statement.order_by(CRMMah.name, CRMMah.id), page, request, "mahs")
    mahs = [mah for (mah,) in rows]
    logos = {}
    key = get_settings().logo_dev_publishable_key
    if key and mahs:
        source_ids = {
            mah.source_row_id
            for mah in mahs
            if mah.source_row_id and "domain" not in (mah.profile or {})
        }
        sources = (
            {
                row.id: row.raw_row_json.get("Domain", "")
                for row in session.scalars(
                    select(StagingRow).where(StagingRow.id.in_(source_ids))
                )
            }
            if source_ids
            else {}
        )
        logos = {
            mah.id: logo_url(
                (mah.profile or {}).get("domain", sources.get(mah.source_row_id, "")),
                key,
                size=48,
            )
            for mah in mahs
        }
    agreement_statuses = defaultdict(list)
    if mahs:
        for mah_id, status in session.execute(
            select(CRMAgreementMAH.mah_id, CRMAgreement.status)
            .join(CRMAgreementMAH)
            .where(CRMAgreementMAH.mah_id.in_([mah.id for mah in mahs]))
            .distinct()
            .order_by(CRMAgreement.status)
        ):
            agreement_statuses[mah_id].append(status)
    directory_scope = (
        CRMMah.archived_at.is_not(None) if archived else CRMMah.archived_at.is_(None)
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_mahs.html",
        context={
            **list_catalogue_context(request, session, "mahs", mahs),
            "title": "CRM · MAHs",
            "active": "crm",
            "crm_section": True,
            "imported_at": crm_imported_at(session, "MAH"),
            "directory_total": session.scalar(
                select(func.count()).select_from(CRMMah).where(directory_scope)
            ),
            "checked_total": session.scalar(
                select(func.count())
                .select_from(CRMMah)
                .where(directory_scope, CRMMah.registration_checked == 1)
            ),
            "rows": mahs,
            "logos": logos,
            "pagination": pagination,
            "q": q,
            "archived": archived,
            "agreement_filter": agreement,
            "agreement_statuses": agreement_statuses,
        },
    )


@router.get("/crm/mahs/new", include_in_schema=False)
def new_crm_mah(request: Request, session: DbSession):
    return render_mah(request, session)


@router.get("/crm/mahs/{identifier}", include_in_schema=False)
def crm_mah_detail(
    request: Request, identifier: int, session: DbSession, edit: str = ""
):
    mah = session.get(CRMMah, identifier)
    if not mah:
        raise HTTPException(404, "MAH not found.")
    source = session.get(StagingRow, mah.source_row_id) if mah.source_row_id else None
    return render_mah(
        request, session, mah, source.raw_row_json if source else None, edit=edit
    )


@router.post("/crm/mahs/{identifier}/transfer", include_in_schema=False)
async def transfer_crm_mah(request: Request, identifier: int, session: DbSession):
    data = await review_form(request)
    raw_target = data.get("target_mah_id", "")
    note = data.get("note", "").strip()
    if not re.fullmatch(r"[0-9]{1,10}", raw_target) or len(note) > 2000:
        raise HTTPException(
            422, "Select a target MAH and enter at most 2,000 characters."
        )
    target_id = int(raw_target)
    if identifier == target_id:
        raise HTTPException(422, "Select a different target MAH.")

    records = {
        mah.id: mah
        for mah in session.scalars(
            select(CRMMah)
            .where(CRMMah.id.in_((identifier, target_id)))
            .order_by(CRMMah.id)
            .with_for_update()
        )
    }
    source, target = records.get(identifier), records.get(target_id)
    if source is None or target is None:
        raise HTTPException(404, "MAH not found.")
    existing = session.get(CRMMahTransfer, identifier, with_for_update=True)
    if existing and existing.target_mah_id == target_id and existing.note == note:
        return RedirectResponse(f"/crm/mahs/{target_id}#transfers", status_code=303)
    if source.archived_at or existing or data.get("version") != str(source.version):
        raise HTTPException(
            409,
            "This MAH changed or has already been transferred. Reload before continuing.",
        )
    if target.archived_at or session.get(
        CRMMahTransfer, target_id, with_for_update=True
    ):
        raise HTTPException(422, "Choose a target MAH that is available for transfer.")

    agreement_ids = selected_ids(data, "transfer_agreement:")
    agreements = (
        list(
            session.scalars(
                select(CRMAgreement)
                .where(CRMAgreement.id.in_(agreement_ids))
                .order_by(CRMAgreement.id)
                .with_for_update()
            )
        )
        if agreement_ids
        else []
    )
    if len(agreements) != len(agreement_ids) or any(
        source not in agreement.mahs or agreement.status != "Signed"
        for agreement in agreements
    ):
        raise HTTPException(
            409, "An agreement changed. Reload and review the transfer selection."
        )
    for agreement in agreements:
        agreement.status = "Transferred"

    now = utcnow()
    source.profile = (source.profile or {}) | {"status": "Transferred"}
    source.updated_at = now
    session.add(
        CRMMahTransfer(
            source_mah_id=identifier, target_mah_id=target_id, note=note, created_at=now
        )
    )
    session.commit()
    return RedirectResponse(f"/crm/mahs/{target_id}#transfers", status_code=303)


@router.post("/crm/mahs/{identifier}/summary-draft", include_in_schema=False)
async def mah_summary_draft(request: Request, identifier: int, session: DbSession):
    await review_form(request)
    settings = get_settings()
    if not settings.openai_api_key or not settings.openai_web_model:
        raise HTTPException(
            503, "Configure OpenAI web research before drafting a summary."
        )
    mah = session.get(CRMMah, identifier)
    if not mah or mah.archived_at:
        raise HTTPException(404, "Active MAH not found.")
    staged = session.get(StagingRow, mah.source_row_id) if mah.source_row_id else None
    source = staged.raw_row_json if staged else None
    domain = (profile_defaults(source or {}) | (mah.profile or {}))["domain"]
    try:
        draft = await run_in_threadpool(
            draft_company_summary, mah.name, domain, settings
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(
            502, "A sourced summary could not be generated. Try again later."
        ) from None
    return render_mah(
        request, session, mah, source, edit="company-summary", summary_draft=draft
    )


def render_mah(request, session, mah=None, source=None, *, edit="", summary_draft=None):
    companies = select(CRMMah.id, CRMMah.name, CRMMah.archived_at)
    if mah:
        companies = companies.where(CRMMah.id != mah.id)
    saved_profile = mah.profile or {} if mah else {}
    profile = profile_defaults(source or {}) | saved_profile
    if "association" in saved_profile and "associations" not in saved_profile:
        profile["associations"] = association_values(saved_profile["association"])
    parent = (
        session.get(CRMMah, mah.parent_company_id)
        if mah and mah.parent_company_id
        else None
    )
    edit_section = edit if mah and not mah.archived_at and edit in EDIT_SECTIONS else ""
    assigned_ids = set(profile.get("alert_contact_ids", [])) | set(spoc_ids(profile))
    contacts = []
    if edit_section == "contacts" or assigned_ids:
        statement = select(CRMContact).order_by(CRMContact.label, CRMContact.id)
        statement = statement.where(
            or_(CRMContact.archived_at.is_(None), CRMContact.id.in_(assigned_ids))
            if edit_section == "contacts"
            else CRMContact.id.in_(assigned_ids)
        )
        contacts = list(session.scalars(statement))
    agreements = (
        list(
            session.scalars(
                select(CRMAgreement)
                .where(CRMAgreement.mahs.any(CRMMah.id == mah.id))
                .order_by(CRMAgreement.contract_id)
            )
        )
        if mah
        else []
    )
    editing_agreement = None
    if edit == "contract" and mah and not mah.archived_at:
        selected = request.query_params.get("agreement_id")
        editing_agreement = next(
            (item for item in agreements if str(item.id) == selected), None
        )
        if editing_agreement:
            edit_section = "contract"
    editing_contract_links = bool(
        edit == "contract-links" and mah and not mah.archived_at
    )
    if editing_contract_links:
        edit_section = "contract-links"
    agreement_options = (
        list(
            session.scalars(
                select(CRMAgreement).order_by(
                    CRMAgreement.contractor, CRMAgreement.contract_id
                )
            )
        )
        if editing_contract_links
        else []
    )
    candidates = agreement_candidates(session) if editing_contract_links else {}
    candidate_agreement_ids = {
        item.id
        for item in agreement_options
        if any(
            candidate.id == mah.id for candidate in candidates.get(item.contract_id, [])
        )
    }
    agreement_options.sort(key=lambda item: item.id not in candidate_agreement_ids)
    outgoing_transfer = session.get(CRMMahTransfer, mah.id) if mah else None
    incoming_transfers = (
        session.execute(
            select(CRMMahTransfer, CRMMah.name)
            .join(CRMMah, CRMMah.id == CRMMahTransfer.source_mah_id)
            .where(CRMMahTransfer.target_mah_id == mah.id)
            .order_by(CRMMahTransfer.created_at.desc(), CRMMahTransfer.source_mah_id)
        ).all()
        if mah
        else []
    )
    transfer_targets = []
    if mah and not mah.archived_at and not outgoing_transfer and not edit_section:
        transferred_ids = select(CRMMahTransfer.source_mah_id)
        transfer_targets = session.execute(
            select(CRMMah.id, CRMMah.name)
            .where(
                CRMMah.id != mah.id,
                CRMMah.archived_at.is_(None),
                CRMMah.id.not_in(transferred_ids),
            )
            .order_by(CRMMah.name, CRMMah.id)
        ).all()
    transfer_agreements = (
        [
            (agreement, len(agreement.mahs) > 1)
            for agreement in agreements
            if agreement.status == "Signed"
        ]
        if transfer_targets
        else []
    )
    settings = get_settings()
    return_context = {
        "edit_section": edit_section,
        "agreements": agreements,
        "editing_agreement": editing_agreement,
        "incoming_transfers": incoming_transfers,
        "outgoing_transfer": outgoing_transfer,
        "transfer_targets": transfer_targets,
        "self_declaration_count": session.scalar(
            select(func.count())
            .select_from(CRMSelfDeclaration)
            .where(CRMSelfDeclaration.mah_id == mah.id)
        )
        if mah
        else 0,
        "transfer_agreements": transfer_agreements,
        "editing_contract_links": editing_contract_links,
        "agreement_options": agreement_options,
        "linked_agreement_ids": {item.id for item in agreements},
        "candidate_agreement_ids": candidate_agreement_ids,
        "agreement_statuses": tuple(
            dict.fromkeys((*AGREEMENT_STATUSES, editing_agreement.status))
        )
        if editing_agreement
        else (),
        "summary_draft": summary_draft,
        "web_research_enabled": bool(
            getattr(settings, "openai_api_key", None)
            and getattr(settings, "openai_web_model", None)
        ),
        "contact_options": contacts,
        "assigned_contacts": {
            contact.id: contact for contact in contacts if contact.id in assigned_ids
        },
        "parent_company": parent,
        "companies": session.execute(companies.order_by(CRMMah.name, CRMMah.id)).all()
        if mah is None or edit_section == "general"
        else [],
        "profile_groups": PROFILE_GROUPS,
        "profile": profile,
        "spoc_ids": spoc_ids(profile),
        "association_options": sorted(
            set(ASSOCIATIONS) | set(profile["associations"]), key=str.casefold
        ),
        "logo_url": logo_url(profile["domain"], settings.logo_dev_publishable_key),
        "billing_parent": parent if not profile["eligible_for_invoicing"] else None,
    }
    query = filter_query(request, "q", "agreement")
    back_query = query + (
        ("&" if query else "?") + "archived=true" if mah and mah.archived_at else ""
    )
    navigation = record_navigation(
        "/crm/mahs", "MAHs", query=query, back_query=back_query
    )
    if mah and not edit_section:
        navigation = crm_navigation(
            request, session,
            mah_directory_statement(
                request.query_params.get("q", ""),
                bool(mah.archived_at),
                request.query_params.get("agreement", ""),
            ),
            CRMMah.id,
            mah.id,
            (CRMMah.name, CRMMah.id),
            "/crm/mahs",
            "MAHs",
            query=query,
            back_query=back_query,
        )
    return templates.TemplateResponse(
        request=request,
        name="crm_mah_detail.html",
        context={
            "title": mah.name if mah else "New MAH",
            "active": "crm",
            "crm_section": True,
            **return_context,
            "mah": mah,
            "record_nav": navigation,
            "source": source,
        },
    )


def form_fields(data):
    name, gln, uid = (data.get(field, "").strip() for field in ("name", "gln", "uid"))
    checked = {"unknown": None, "yes": 1, "no": 0}
    registration = data.get("registration_checked")
    contract = data.get("contract_status", "unknown")
    if not name or len(name) > 255 or max(len(gln), len(uid)) > 100:
        raise HTTPException(422, "Provide a name and valid field lengths.")
    if registration not in checked or contract not in CONTRACT_STATUSES:
        raise HTTPException(422, "Select valid registration and contract statuses.")
    return {
        "name": name,
        "gln": gln or None,
        "uid": uid or None,
        "registration_checked": checked[registration],
        "contract_status": contract,
    }


def profile_fields(data, session, identifier=None):
    parent_id = data.get("parent_company_id", "")
    parent = None
    if parent_id:
        if not parent_id.isascii() or not parent_id.isdecimal() or len(parent_id) > 10:
            raise HTTPException(422, "Select a valid parent company.")
        parent = session.get(CRMMah, int(parent_id), with_for_update=True)
        if parent is None:
            raise HTTPException(422, "Select a valid parent company.")
        ancestor = parent
        seen = {identifier}
        while ancestor:
            if ancestor.id in seen:
                raise HTTPException(422, "Parent companies cannot form a cycle.")
            seen.add(ancestor.id)
            ancestor = (
                session.get(CRMMah, ancestor.parent_company_id, with_for_update=True)
                if ancestor.parent_company_id
                else None
            )

    profile = {
        field: data.get(field, "")
        for group in PROFILE_GROUPS.values()
        for field, _, _ in group
        if field in data
    }
    if data.get("invoice_routing_present") == "yes":
        profile["eligible_for_invoicing"] = data.get("eligible_for_invoicing") == "yes"
    if data.get("associations_present") == "yes":
        profile["associations"] = association_values(
            [
                field.removeprefix("association:")
                for field, value in data.items()
                if field.startswith("association:") and value == "yes"
            ]
        )
    elif "association" in data:
        profile["associations"] = association_values(data["association"])
    profile["payment_platform"] = data.get("payment_platform") == "yes"
    signing_date = data.get("signing_date", "")
    if signing_date:
        try:
            signing_date = date.fromisoformat(signing_date).isoformat()
        except ValueError:
            raise HTTPException(422, "Enter a valid signing date.") from None
    profile["signing_date"] = signing_date
    return {"profile": profile, "parent_company_id": parent.id if parent else None}


def contact_assignments(data, session, profile):
    spocs = data.get("spoc_ids", data.get("spoc_id", ""))
    alerts = data.get("alert_contact_ids", "")
    submitted = (spocs.split(",") if spocs else []) + (
        alerts.split(",") if alerts else []
    )
    if any(
        not value.isascii() or not value.isdecimal() or len(value) > 10
        for value in submitted
    ):
        raise HTTPException(422, "Select existing contacts.")
    ids = set(map(int, submitted))
    profile = profile or {}
    existing_spocs = set(spoc_ids(profile))
    existing_alerts = set(profile.get("alert_contact_ids", []))
    spoc_selection = list(dict.fromkeys(map(int, spocs.split(",")))) if spocs else []
    alert_selection = list(dict.fromkeys(map(int, alerts.split(",")))) if alerts else []
    contacts = (
        {
            contact.id: contact
            for contact in session.scalars(
                select(CRMContact)
                .where(CRMContact.id.in_(ids))
                .order_by(CRMContact.id)
                .with_for_update()
            )
        }
        if ids
        else {}
    )
    if ids != contacts.keys() or any(
        contacts[identifier].archived_at and identifier not in existing
        for selection, existing in (
            (spoc_selection, existing_spocs),
            (alert_selection, existing_alerts),
        )
        for identifier in selection
    ):
        raise HTTPException(422, "Select active contacts for new assignments.")
    saved = dict(profile or {})
    saved.pop("spoc_id", None)
    saved["spoc_ids"] = spoc_selection
    saved["alert_contact_ids"] = alert_selection
    return saved


def section_fields(data, session, mah, section):
    if section not in EDIT_SECTIONS:
        raise HTTPException(422, "Select a valid MAH section.")
    if section == "contacts":
        return {"profile": contact_assignments(data, session, mah.profile)}
    fields = {}
    if section == "general":
        fields = form_fields({**data, "contract_status": mah.contract_status})
    allowed = {field for field, _, _ in PROFILE_GROUPS.get(EDIT_SECTIONS[section], ())}
    if section == "general":
        allowed.update({"parent_company_id", "associations_present"})
        allowed.update(field for field in data if field.startswith("association:"))
    elif section == "invoice":
        allowed.update(
            {"invoice_routing_present", "eligible_for_invoicing", "payment_platform"}
        )

    changes = profile_fields(
        {field: data[field] for field in allowed if field in data}, session, mah.id
    )
    profile = changes["profile"]
    if section != "invoice":
        profile.pop("payment_platform")
    profile.pop("signing_date")
    if section == "general":
        fields["parent_company_id"] = changes["parent_company_id"]
    fields["profile"] = (mah.profile or {}) | profile
    return fields


@router.post("/crm/mahs", include_in_schema=False)
async def create_crm_mah(request: Request, session: DbSession):
    data = await review_form(request)
    fields = form_fields(data)
    fields.update(profile_fields(data, session))
    now = utcnow()
    mah = CRMMah(**fields, created_at=now, updated_at=now)
    session.add(mah)
    session.commit()
    return RedirectResponse(f"/crm/mahs/{mah.id}", status_code=303)


@router.post("/crm/mahs/{identifier}", include_in_schema=False)
async def update_crm_mah(request: Request, identifier: int, session: DbSession):
    data = await review_form(request)
    mah = session.get(CRMMah, identifier, with_for_update=True)
    if not mah:
        raise HTTPException(404, "MAH not found.")
    if data.get("version") != str(mah.version):
        raise HTTPException(409, "This MAH changed. Reload before saving.")
    command = data.get("command")
    now = utcnow()
    if command == "save" and mah.archived_at is None:
        section = data.get("section")
        if section == "contract-links":
            selected = selected_ids(data, "agreement:")
            linked = select(CRMAgreementMAH.agreement_id).where(
                CRMAgreementMAH.mah_id == mah.id
            )
            agreements = list(
                session.scalars(
                    select(CRMAgreement)
                    .where(
                        or_(CRMAgreement.id.in_(selected), CRMAgreement.id.in_(linked))
                    )
                    .order_by(CRMAgreement.id)
                    .with_for_update()
                )
            )
            if not selected.issubset({agreement.id for agreement in agreements}):
                raise HTTPException(422, "Choose valid agreements.")
            for agreement in agreements:
                if agreement.id in selected and mah not in agreement.mahs:
                    agreement.mahs.append(mah)
                elif agreement.id not in selected and mah in agreement.mahs:
                    agreement.mahs.remove(mah)
            fields = {}
        elif section == "contract":
            value = data.get("agreement_id", "")
            if not re.fullmatch(r"[0-9]{1,10}", value):
                raise HTTPException(422, "Choose a valid agreement.")
            agreement = agreement_or_404(session, int(value), lock=True)
            if mah not in agreement.mahs:
                raise HTTPException(
                    409, "This agreement is no longer linked to this MAH."
                )
            update_agreement_details(agreement, data)
            fields = {}
        elif section is not None:
            fields = section_fields(data, session, mah, section)
        else:
            fields = form_fields(data)
            if data.get("edit_profile") == "yes":
                changes = profile_fields(data, session, mah.id)
                changes["profile"] = (mah.profile or {}) | changes["profile"]
                fields.update(changes)
        for field, value in fields.items():
            setattr(mah, field, value)
    elif command == "archive" and mah.archived_at is None:
        mah.archived_at = now
    elif command == "restore" and mah.archived_at is not None:
        mah.archived_at = None
    else:
        raise HTTPException(
            409, "This action is unavailable for the current MAH state."
        )
    mah.updated_at = now
    try:
        session.commit()
    except StaleDataError:
        session.rollback()
        raise HTTPException(409, "This MAH changed. Reload before saving.") from None
    if command == "archive":
        return RedirectResponse("/crm/mahs?archived=true", status_code=303)
    query = filter_query(request, "q", "agreement")
    if command == "save" and data.get("section") == "company-summary":
        query += ("&" if query else "?") + "summary=open#company-summary"
    if command == "save" and data.get("section") in ("contract", "contract-links"):
        query += "#contract"
    return RedirectResponse(f"/crm/mahs/{identifier}{query}", status_code=303)
