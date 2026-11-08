"""CRM business fields shared by list columns and future typed view conditions."""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select

from app.core.db.models import StagingRow
from app.domain.crm.contact_assignments import spoc_ids
from app.domain.crm.imports import linked_values
from app.domain.crm.mah_profile import PROFILE_GROUPS, profile_defaults
from app.domain.models import (
    CRMAgreement,
    CRMAgreementMAH,
    CRMContact,
    CRMEndUser,
    CRMMah,
    LocalOrganisation,
)

DEFAULT_COLUMNS = {
    "mahs": ("name", "gln", "uid", "registration", "contract"),
    "contacts": ("name", "function"),
    "end-users": ("name", "organisation", "link"),
    "it-suppliers": ("name", "status", "qualified", "software"),
    "agreements": ("contract_id", "contractor", "status", "mah", "pdfs"),
    "self-declarations": ("declaration", "year", "mah", "packs", "status"),
}


@dataclass(frozen=True)
class CRMField:
    key: str
    label: str
    kind: str = "text"
    header: str | None = None
    origin: str = "CRM"

    @property
    def operators(self):
        return {
            "text": ("equals", "contains", "empty", "not_empty"),
            "list": ("contains", "empty", "not_empty"),
            "boolean": ("equals", "empty", "not_empty"),
            "number": ("equals", "less_than", "greater_than", "empty", "not_empty"),
            "date": ("equals", "before", "after", "empty", "not_empty"),
        }[self.kind]


def imported_fields(headers):
    # Retained source-only values are explicit and keep their original text.
    return tuple(
        CRMField(
            "source_" + re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_"),
            header,
            header=header,
            origin="Airtable import",
        )
        for header in headers
    )


CATALOGUE = {
    "mahs": (
        CRMField("name", "MAH"),
        CRMField("gln", "GLN"),
        CRMField("uid", "UID"),
        CRMField("registration", "Registration check"),
        CRMField("contract", "Contract status", "list"),
        *(
            CRMField(key, label, header=header)
            for group in PROFILE_GROUPS.values()
            for key, label, header in group
        ),
        CRMField("parent_company", "Parent company"),
        CRMField("associations", "Industry association memberships", "list"),
        CRMField("spocs", "SPOCs", "list"),
        CRMField("alert_contacts", "Alert contacts", "list"),
        CRMField(
            "eligible_for_invoicing", "Eligible for invoice", "boolean"
        ),
        CRMField(
            "payment_platform", "Submit invoices via a payment platform", "boolean"
        ),
        CRMField("signing_date", "Signing dates", "list", origin="Agreements"),
        CRMField("agreements", "Agreements", "list", origin="Agreements"),
        CRMField(
            "agreement_count", "Number of agreements", "number", origin="Agreements"
        ),
        CRMField("archived_at", "Archived at", "date"),
        CRMField("created_at", "Created at", "date"),
        CRMField("updated_at", "Updated at", "date"),
        *imported_fields(
            (
                "Marketing Authorization in Switzerland",
                "Email general",
                "One-time fee charged",
                "Tasks",
                "Industry",
                "Headquarters Location",
                "Contacts",
                "Selfdeclarations",
                "Logo",
                "Invoices",
                "Created Time",
                "Last modified time",
                "Modified Time",
                "Email Payment Inquiries",
            )
        ),
    ),
    "contacts": (
        CRMField("name", "Contact"),
        CRMField("function", "Function", "list"),
        CRMField("first_name", "First name", header="First Name"),
        CRMField("last_name", "Last name", header="Last Name"),
        CRMField("email", "Email", header="Email"),
        CRMField("phone", "Phone", header="Phone"),
        CRMField("address_type", "Address type"),
        CRMField("mailbox_type", "Mailbox type", header="Mailbox Type"),
        CRMField("assigned_mahs", "Assigned MAHs", "list"),
        CRMField("assigned_end_users", "Assigned End Users", "list"),
        CRMField("archived_at", "Archived at", "date"),
        *imported_fields(
            ("Link MAH", "Link End Users", "Link IT Supplier", "Communications")
        ),
    ),
    "end-users": (
        CRMField("name", "End User"),
        CRMField("organisation", "NMVS organisation", origin="NMVS"),
        CRMField("link", "Link status"),
        CRMField("software", "Software product", header="Software Product"),
        CRMField("supplier", "IT supplier", header="Enduser Software Supplier"),
        CRMField("email", "Email", header="Email general"),
        CRMField("phone", "Phone", header="Phone"),
        CRMField("spocs", "SPOCs", "list"),
        CRMField("alert_contacts", "Alert contacts", "list"),
        CRMField("archived_at", "Archived at", "date"),
        *imported_fields(
            (
                "Organisation type",
                "Street",
                "City",
                "Postal code",
                "Country",
                "Domain",
                "GLN",
                "UID",
                "Authorisation Checked",
                "Logo",
                "Authorisation Number",
                "Status",
            )
        ),
    ),
    "it-suppliers": (
        CRMField(
            "name", "IT Supplier", header="IT Supplier Name", origin="Airtable import"
        ),
        CRMField("status", "Status", header="Status", origin="Airtable import"),
        CRMField(
            "qualified", "Qualified", header="Qualified", origin="Airtable import"
        ),
        CRMField(
            "software",
            "End-user software",
            header="End User Software",
            origin="Airtable import",
        ),
        *imported_fields(
            (
                "Phone",
                "Domain",
                "Created Time",
                "Modified Time",
                "Street",
                "City",
                "Postal code",
                "Country",
                "Additional address information",
                "GLN",
                "UID",
                "Email general",
                "Tasks",
                "Company Size",
                "Industry",
                "Headquarters Location",
                "Contacts",
                "SPOC",
                "Logo URL",
                "Logo",
                "Company summary",
                "Target Group",
            )
        ),
    ),
    "agreements": (
        CRMField("contract_id", "Contract ID"),
        CRMField("contractor", "Contractor"),
        CRMField("status", "Status"),
        CRMField("mah", "Assigned MAHs", "list"),
        CRMField("pdfs", "PDFs", "number"),
        CRMField("signing_date", "Signing date", "date"),
        *imported_fields(
            (
                "Start Date",
                "Type",
                "Minimum Term (Years)",
                "Minimum Term End Date",
                "Termination Notice (Months)",
                "Auto-Renewal",
                "Created By",
                "Created Time",
                "Last Modified",
                "Next Possible Termination Date",
                "Counterparty",
                "Notes",
                "Tasks",
                "End Users",
                "Affiliates",
                "Termination Date",
            )
        ),
    ),
    "self-declarations": (
        CRMField("declaration", "Declaration"),
        CRMField("year", "Data year", "number"),
        CRMField("mah", "MAH"),
        CRMField("packs", "RX packs sold", "number"),
        CRMField("status", "Imported status", origin="Airtable import"),
        CRMField("invoice_year", "Invoice year", "number", origin="Derived"),
        *imported_fields(
            (
                "Quantity related amount",
                "Invoice number",
                "RX sales group",
                "Sales related amount",
                "RX quantity group",
                "Base fee code",
                "Base fee amount",
            )
        ),
    ),
}


def field_keys(view):
    return tuple(field.key for field in CATALOGUE[view])


def display_value(value):
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return (
            ", ".join(
                dict.fromkeys(
                    str(item) for item in value if item is not None and item != ""
                )
            )
            or "—"
        )
    return str(value)


def catalogue_context(session, view, records, *, pdf_counts=None):
    """Batch-load source and relation values for one result page."""
    fields = CATALOGUE[view]
    extras = [field for field in fields if field.key not in DEFAULT_COLUMNS[view]]
    source_ids = {
        record.source_row_id
        for record in records
        if getattr(record, "source_row_id", None)
    }
    sources = (
        dict(
            session.execute(
                select(StagingRow.id, StagingRow.raw_row_json).where(
                    StagingRow.id.in_(source_ids)
                )
            ).all()
        )
        if source_ids
        else {}
    )
    contacts = {}
    parents = {}
    agreements = defaultdict(list)
    agreement_mahs = defaultdict(list)
    assigned_mahs, assigned_end_users = defaultdict(list), defaultdict(list)
    organisations = {}
    if view in {"mahs", "end-users"}:
        contact_ids = set()
        for record in records:
            profile = record.profile or {}
            contact_ids.update(spoc_ids(profile))
            contact_ids.update(profile.get("alert_contact_ids", []))
        if contact_ids:
            contacts = {
                contact.id: contact.display_name
                for contact in session.scalars(
                    select(CRMContact).where(CRMContact.id.in_(contact_ids))
                )
            }
    if view == "mahs" and records:
        parent_ids = {
            record.parent_company_id for record in records if record.parent_company_id
        }
        if parent_ids:
            parents = dict(
                session.execute(
                    select(CRMMah.id, CRMMah.name).where(CRMMah.id.in_(parent_ids))
                ).all()
            )
        for mah_id, agreement in session.execute(
            select(CRMAgreementMAH.mah_id, CRMAgreement)
            .join(CRMAgreement)
            .where(CRMAgreementMAH.mah_id.in_([record.id for record in records]))
            .order_by(CRMAgreement.contract_id)
        ):
            agreements[mah_id].append(agreement)
    if view == "agreements" and records:
        for agreement_id, name in session.execute(
            select(CRMAgreementMAH.agreement_id, CRMMah.name)
            .join(CRMMah)
            .where(CRMAgreementMAH.agreement_id.in_([record.id for record in records]))
            .order_by(CRMMah.name, CRMMah.id)
        ):
            agreement_mahs[agreement_id].append(name)
    if view == "contacts" and records:
        ids = {record.id for record in records}
        for model, target in (
            (CRMMah, assigned_mahs),
            (CRMEndUser, assigned_end_users),
        ):
            for entity in session.scalars(
                select(model).where(model.archived_at.is_(None))
            ):
                profile = entity.profile or {}
                for identifier in (
                    set(spoc_ids(profile)) | set(profile.get("alert_contact_ids", []))
                ) & ids:
                    target[identifier].append(entity.name)
    if view == "end-users" and records:
        organisation_ids = {
            record.organisation_id for record in records if record.organisation_id
        }
        if organisation_ids:
            organisations = {
                entity.id: entity.organisation_name
                for entity in session.scalars(
                    select(LocalOrganisation).where(
                        LocalOrganisation.id.in_(organisation_ids)
                    )
                )
            }
    if view == "self-declarations" and records:
        ids = {record.mah_id for record in records if record.mah_id}
        if ids:
            parents = dict(
                session.execute(
                    select(CRMMah.id, CRMMah.name).where(CRMMah.id.in_(ids))
                ).all()
            )
    cells = {}
    raw_values = {}
    for record in records:
        raw = (
            record.raw_row_json
            if view == "it-suppliers"
            else sources.get(record.source_row_id, {})
        )
        profile = (
            record.profile or {} if view in {"mahs", "contacts", "end-users"} else {}
        )
        if view == "mahs":
            profile = profile_defaults(raw) | profile
        values = {
            field.key: profile.get(field.key, raw.get(field.header, ""))
            for field in fields
        }
        if view in {"mahs", "end-users"}:
            values.update(
                spocs=[
                    contacts[identifier]
                    for identifier in spoc_ids(profile)
                    if identifier in contacts
                ],
                alert_contacts=[
                    contacts[id]
                    for id in profile.get("alert_contact_ids", [])
                    if id in contacts
                ],
            )
        if view == "mahs":
            linked = agreements[record.id]
            values.update(
                name=record.name,
                gln=record.gln,
                uid=record.uid,
                registration=(
                    "Checked"
                    if record.registration_checked == 1
                    else (
                        "Not checked" if record.registration_checked == 0 else "Unknown"
                    )
                ),
                parent_company=parents.get(record.parent_company_id),
                contract=[item.status for item in linked],
                agreements=[item.contract_id for item in linked],
                signing_date=[
                    item.signing_date for item in linked if item.signing_date
                ],
                agreement_count=len(linked),
                archived_at=record.archived_at,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        elif view == "contacts":
            values.update(
                name=record.display_name,
                function=linked_values(record.function or ""),
                assigned_mahs=assigned_mahs[record.id],
                assigned_end_users=assigned_end_users[record.id],
                archived_at=record.archived_at,
            )
            if not values["email"] and "email" not in profile and "@" in record.label:
                values["email"] = record.label
        elif view == "end-users":
            values.update(
                name=record.name,
                organisation=organisations.get(record.organisation_id),
                link="Unlinked"
                if not record.organisation_id
                else "Exact match"
                if record.link_origin == "exact"
                else "Manually linked",
                archived_at=record.archived_at,
            )
        elif view == "agreements":
            values.update(
                contract_id=record.contract_id,
                contractor=record.contractor,
                status=record.status,
                signing_date=record.signing_date,
                mah=agreement_mahs[record.id],
                pdfs=(pdf_counts or {}).get(record.contract_id, 0),
            )
        elif view == "self-declarations":
            values.update(
                declaration=record.record_label,
                year=record.declaration_year,
                invoice_year=record.declaration_year + 1,
                mah=parents.get(record.mah_id, record.source_mah_name),
                packs=record.packs_sold,
                status=record.status,
            )
        raw_values[record.id] = values
        cells[record.id] = {key: display_value(value) for key, value in values.items()}
    return {
        "crm_extra_columns": extras,
        "crm_field_cells": cells,
        "crm_field_values": raw_values,
    }
