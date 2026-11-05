import csv
import io
import re
from collections import Counter, defaultdict
from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.core.db.models import (
    AcquiredArtifact,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.domain.crm.contacts import MAILBOX_TYPES
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
from app.domain.models import (
    CRMContact,
    CRMEndUser,
    CRMMah,
    EndUserImportReview,
    LocalOrganisation,
)
from app.integration.artifacts.storage import utcnow
from app.portal.exception_routes import review_form
from app.portal.queries import paged
from app.portal.record_navigation import (
    filter_query,
    list_record_navigation,
    record_navigation,
)
from app.portal.routes import DbSession, templates

router = APIRouter()

EDIT_SECTIONS = {
    "general": "General",
    "address": "Address",
    "invoice": "Invoice information",
    "contract": "Contract",
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


def end_user_filter_query(q, unlinked, archived=False):
    filters = {}
    if q:
        filters["q"] = q
    if unlinked:
        filters["unlinked"] = "true"
    if archived:
        filters["archived"] = "true"
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
    rows, pagination = paged(
        session, statement.order_by(CRMEndUser.name, CRMEndUser.id), page
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
            "detail_query": end_user_filter_query(q, unlinked),
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


def end_user_neighbours(session, user, q, unlinked):
    statement = end_user_directory_statement(
        q, unlinked, bool(user.archived_at)
    ).with_only_columns(CRMEndUser.id)
    previous = session.scalar(
        statement.where(
            or_(
                CRMEndUser.name < user.name,
                and_(CRMEndUser.name == user.name, CRMEndUser.id < user.id),
            )
        )
        .order_by(CRMEndUser.name.desc(), CRMEndUser.id.desc())
        .limit(1)
    )
    following = session.scalar(
        statement.where(
            or_(
                CRMEndUser.name > user.name,
                and_(CRMEndUser.name == user.name, CRMEndUser.id > user.id),
            )
        )
        .order_by(CRMEndUser.name, CRMEndUser.id)
        .limit(1)
    )
    return previous, following


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
    ids = set(profile.get("alert_contact_ids", []))
    if profile.get("spoc_id"):
        ids.add(profile["spoc_id"])
    if edit == "contacts" or ids:
        contacts = select(CRMContact).order_by(CRMContact.label, CRMContact.id)
        if edit != "contacts":
            contacts = contacts.where(CRMContact.id.in_(ids))
        contact_options = list(session.scalars(contacts))
    pending_contacts = []
    if source.get("SPOC") or source.get("Alert contacts"):
        _, pending_contacts = resolve_end_user_contacts(
            source, contact_reference_index(session)
        )
    previous, following = (
        end_user_neighbours(session, user, q, unlinked)
        if user and not edit
        else (None, None)
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_end_user_detail.html",
        context={
            "title": user.name if user else "New End User",
            "active": "crm",
            "crm_section": True,
            "user": user,
            "record_nav": record_navigation(
                "/crm/end-users",
                "End Users",
                previous,
                following,
                query=end_user_filter_query(q, unlinked),
                back_query=end_user_filter_query(
                    q, unlinked, bool(user and user.archived_at)
                ),
            ),
            "detail_query": end_user_filter_query(q, unlinked),
            "source": source,
            "profile": profile,
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
        user.profile = (user.profile or {}) | contact_assignments(data, session)
    else:
        raise HTTPException(422, "Select a valid End User action.")
    session.commit()
    destination = (
        f"/crm/end-users{end_user_filter_query(q, unlinked, archived=True)}"
        if command == "archive"
        else f"/crm/end-users/{user.id}{end_user_filter_query(q, unlinked)}"
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
        f"/crm/end-users/{identifier}{end_user_filter_query(q, unlinked)}#organisation",
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
    rows = filtered_suppliers(export[3] if export else [], q)
    return templates.TemplateResponse(
        request=request,
        name="crm_it_suppliers.html",
        context={
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
        for row in filtered_suppliers(export[3], request.query_params.get("q", ""))
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


def contact_directory_statement(q):
    statement = select(CRMContact)
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
    page: int = Query(1, ge=1),
):
    statement = contact_directory_statement(q)
    rows, pagination = paged(
        session, statement.order_by(CRMContact.label, CRMContact.id), page
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_contacts.html",
        context={
            "title": "CRM · Contacts",
            "active": "crm",
            "crm_section": True,
            "imported_at": crm_imported_at(session, "Contacts"),
            "directory_total": session.scalar(
                select(func.count()).select_from(CRMContact)
            ),
            "rows": [contact for (contact,) in rows],
            "q": q,
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
        if contact.id == profile.get("spoc_id") or contact.id in profile.get(
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
        if contact.id == (user.profile or {}).get("spoc_id")
        or contact.id in (user.profile or {}).get("alert_contact_ids", [])
    ]
    export = staged_crm_export(session, "IT Suppliers")
    suppliers = export[3] if export else []
    links, _, pending_suppliers = supplier_contact_links(session, suppliers)
    navigation = (
        list_record_navigation(
            session,
            contact_directory_statement(request.query_params.get("q", "")),
            CRMContact.id,
            identifier,
            (CRMContact.label, CRMContact.id),
            "/crm/contacts",
            "Contacts",
            query=filter_query(request, "q"),
        )
        if edit not in CONTACT_SECTIONS
        else record_navigation(
            "/crm/contacts", "Contacts", query=filter_query(request, "q")
        )
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


def mah_directory_statement(q, archived):
    statement = select(CRMMah).where(
        CRMMah.archived_at.is_not(None) if archived else CRMMah.archived_at.is_(None)
    )
    if q.strip():
        text = q.strip()
        statement = statement.where(
            or_(
                CRMMah.name.contains(text, autoescape=True),
                CRMMah.gln.contains(text, autoescape=True),
                CRMMah.uid.contains(text, autoescape=True),
            )
        )
    return statement


@router.get("/crm/mahs", include_in_schema=False)
def crm_mahs(
    request: Request,
    session: DbSession,
    q: str = Query("", max_length=150),
    archived: bool = False,
    page: int = Query(1, ge=1),
):
    statement = mah_directory_statement(q, archived)
    rows, pagination = paged(session, statement.order_by(CRMMah.name, CRMMah.id), page)
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
    directory_scope = (
        CRMMah.archived_at.is_not(None) if archived else CRMMah.archived_at.is_(None)
    )
    return templates.TemplateResponse(
        request=request,
        name="crm_mahs.html",
        context={
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
            "contract_statuses": CONTRACT_STATUSES,
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


def render_mah(request, session, mah=None, source=None, *, edit=""):
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
    assigned_ids = set(profile.get("alert_contact_ids", []))
    if profile.get("spoc_id"):
        assigned_ids.add(profile["spoc_id"])
    contacts = []
    if edit_section == "contacts" or assigned_ids:
        statement = select(CRMContact).order_by(CRMContact.label, CRMContact.id)
        if edit_section != "contacts":
            statement = statement.where(CRMContact.id.in_(assigned_ids))
        contacts = list(session.scalars(statement))
    return_context = {
        "edit_section": edit_section,
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
        "association_options": sorted(
            set(ASSOCIATIONS) | set(profile["associations"]), key=str.casefold
        ),
        "logo_url": logo_url(
            profile["domain"], get_settings().logo_dev_publishable_key
        ),
        "billing_parent": parent if not profile["eligible_for_invoicing"] else None,
    }
    query = filter_query(request, "q")
    back_query = query + (
        ("&" if query else "?") + "archived=true" if mah and mah.archived_at else ""
    )
    navigation = record_navigation(
        "/crm/mahs", "MAHs", query=query, back_query=back_query
    )
    if mah and not edit_section:
        navigation = list_record_navigation(
            session,
            mah_directory_statement(
                request.query_params.get("q", ""), bool(mah.archived_at)
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
            "contract_statuses": CONTRACT_STATUSES,
        },
    )


def form_fields(data):
    name, gln, uid = (data.get(field, "").strip() for field in ("name", "gln", "uid"))
    checked = {"unknown": None, "yes": 1, "no": 0}
    registration = data.get("registration_checked")
    contract = data.get("contract_status")
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


def contact_assignments(data, session):
    spoc = data.get("spoc_id", "")
    alerts = data.get("alert_contact_ids", "")
    submitted = ([spoc] if spoc else []) + (alerts.split(",") if alerts else [])
    if any(
        not value.isascii() or not value.isdecimal() or len(value) > 10
        for value in submitted
    ):
        raise HTTPException(422, "Select existing contacts.")
    alert_ids = list(dict.fromkeys(map(int, alerts.split(",")))) if alerts else []
    spoc_id = int(spoc) if spoc else None
    ids = set(map(int, submitted))
    if (
        ids
        and set(session.scalars(select(CRMContact.id).where(CRMContact.id.in_(ids))))
        != ids
    ):
        raise HTTPException(422, "Select existing contacts.")
    return {"spoc_id": spoc_id, "alert_contact_ids": alert_ids}


def section_fields(data, session, mah, section):
    if section not in EDIT_SECTIONS:
        raise HTTPException(422, "Select a valid MAH section.")
    if section == "contacts":
        return {"profile": (mah.profile or {}) | contact_assignments(data, session)}
    fields = {}
    if section == "general":
        fields = form_fields({**data, "contract_status": mah.contract_status})
    elif section == "contract":
        contract = data.get("contract_status")
        if contract not in CONTRACT_STATUSES:
            raise HTTPException(422, "Select a valid contract status.")
        fields["contract_status"] = contract

    allowed = {field for field, _, _ in PROFILE_GROUPS.get(EDIT_SECTIONS[section], ())}
    if section == "general":
        allowed.update({"parent_company_id", "associations_present"})
        allowed.update(field for field in data if field.startswith("association:"))
    elif section == "invoice":
        allowed.update(
            {"invoice_routing_present", "eligible_for_invoicing", "payment_platform"}
        )
    elif section == "contract":
        allowed.add("signing_date")

    changes = profile_fields(
        {field: data[field] for field in allowed if field in data}, session, mah.id
    )
    profile = changes["profile"]
    if section != "invoice":
        profile.pop("payment_platform")
    if section != "contract":
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
        if section is not None:
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
    return RedirectResponse(
        f"/crm/mahs/{identifier}{filter_query(request, 'q')}", status_code=303
    )
