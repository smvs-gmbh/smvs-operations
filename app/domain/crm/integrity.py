"""Read-only CRM integrity findings. No repairs, source rewrites or deliveries."""

import re
from collections import defaultdict

from sqlalchemy import select

from app.core.db.models import StagingDataset, StagingRow
from app.domain.crm.contact_assignments import spoc_ids
from app.domain.crm.declaration_workflow import usable_email
from app.domain.crm.imports import linked_values
from app.domain.crm.mah_profile import profile_defaults
from app.domain.crm.organisation_links import affiliations, migration_plan
from app.domain.models import (
    CRMAgreement,
    CRMAgreementMAH,
    CRMContact,
    CRMEndUser,
    CRMITSupplierIdentity,
    CRMMah,
    CRMSelfDeclaration,
)

RULES = {
    "sd_duplicate": "Duplicate self-declaration for MAH/year",
    "sd_missing": "No self-declaration for selected year",
    "sd_unassigned": "Self-declaration without an MAH",
    "mah_spoc": "MAH without an available SPOC",
    "mah_alert_manager": "MAH without an available Alert Manager",
    "contact_email": "Assigned role contact without a usable email",
    "contact_reference": "Unavailable role contact assignment",
    "contact_orphan": "Contact without a relation",
    "contact_relation": "Unresolved organisation affiliation",
    "contact_source_only": "Contact has imported relations only",
    "mah_identifier": "Repeated MAH GLN or UID",
}


def contact_ids(value):
    return (
        {item for item in value if type(item) is int and item > 0}
        if isinstance(value, (list, tuple))
        else set()
    )


def check_integrity(session, year):
    mahs = list(session.scalars(select(CRMMah).order_by(CRMMah.name, CRMMah.id)))
    contacts = list(session.scalars(select(CRMContact).order_by(CRMContact.id)))
    users = list(session.scalars(select(CRMEndUser)))
    declarations = list(
        session.scalars(select(CRMSelfDeclaration).order_by(CRMSelfDeclaration.id))
    )
    source_ids = {
        r.source_row_id for r in [*mahs, *contacts, *users] if r.source_row_id
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
    current = {m.id: m for m in mahs if not m.archived_at}
    mah_index = {m.id: m for m in mahs}
    contact_index = {c.id: c for c in contacts}
    available = {
        c.id
        for c in contacts
        if not c.archived_at and not (c.profile or {}).get("registration_pending")
    }
    findings = []

    def add(rule, severity, kind, record, detail, links=()):
        paths = {
            "MAH": "mahs",
            "Contact": "contacts",
            "Self-declaration": "self-declarations",
            "End User": "end-users",
            "IT Supplier": "it-suppliers",
        }
        label = (
            record.name
            if kind in {"MAH", "End User", "IT Supplier"}
            else record.display_name
            if kind == "Contact"
            else record.record_label
        )
        findings.append(
            {
                "rule": rule,
                "severity": severity,
                "kind": kind,
                "id": record.id,
                "label": label,
                "detail": detail,
                "url": f"/crm/{paths[kind]}/{record.source_row_id if kind == 'IT Supplier' else record.id}",
                "links": list(links),
            }
        )

    pairs = defaultdict(list)
    for declaration in declarations:
        if declaration.mah_id is None or declaration.mah_id not in mah_index:
            add(
                "sd_unassigned",
                "Error",
                "Self-declaration",
                declaration,
                "Assign this declaration to the correct MAH; no lookup can use it yet.",
            )
        else:
            pairs[declaration.mah_id, declaration.declaration_year].append(declaration)
    for (mah_id, data_year), records in pairs.items():
        if len(records) > 1:
            add(
                "sd_duplicate",
                "Error",
                "MAH",
                mah_index[mah_id],
                f"{len(records)} declarations for data year {data_year}. Exactly one is permitted; lookup values are withheld when this year is selected.",
                [(r.record_label, f"/crm/self-declarations/{r.id}") for r in records],
            )
    signed = set(
        session.scalars(
            select(CRMAgreementMAH.mah_id)
            .join(CRMAgreement)
            .where(CRMAgreement.status == "Signed")
        )
    )
    eligible = set()
    for mah in current.values():
        raw = sources.get(mah.source_row_id, {})
        if mah.id in signed and (mah.profile or {}).get(
            "eligible_for_invoicing", profile_defaults(raw)["eligible_for_invoicing"]
        ):
            eligible.add(mah.id)
            if (mah.id, year) not in pairs:
                add(
                    "sd_missing",
                    "Review",
                    "MAH",
                    mah,
                    f"No declaration for data year {year}. The MAH is in the current signed-agreement/invoice-eligible scope; confirm applicability and timing.",
                )
        for role, identifiers, rule in (
            ("SPOC", spoc_ids(mah.profile), "mah_spoc"),
            (
                "Alert Manager",
                (mah.profile or {}).get("alert_contact_ids", []),
                "mah_alert_manager",
            ),
        ):
            raw_ids = identifiers
            identifiers = contact_ids(raw_ids)
            if raw_ids is not None and (
                not isinstance(raw_ids, (list, tuple))
                or any(type(item) is not int or item <= 0 for item in raw_ids)
            ):
                add(
                    "contact_reference",
                    "Error",
                    "MAH",
                    mah,
                    f"{role} assignment contains an invalid contact reference.",
                )
            if not identifiers & available:
                add(
                    rule,
                    "Error",
                    "MAH",
                    mah,
                    f"Assign at least one non-archived, non-provisional {role}.",
                )
            for identifier in identifiers:
                contact = contact_index.get(identifier)
                if identifier not in available:
                    add(
                        "contact_reference",
                        "Error",
                        "MAH",
                        mah,
                        f"{role} contact #{identifier} is missing, archived or still provisional.",
                    )
                elif contact:
                    raw = sources.get(contact.source_row_id, {})
                    email = (contact.profile or {}).get(
                        "email", raw.get("Email", contact.label)
                    )
                    if not usable_email((email or "").strip()):
                        add(
                            "contact_email",
                            "Review",
                            "Contact",
                            contact,
                            f"Assigned as {role} to {mah.name}, but no usable email is recorded.",
                        )

    assigned = set(affiliations(session))
    imported_references = set()
    contact_refs = defaultdict(set)
    for contact in contacts:
        raw = sources.get(contact.source_row_id, {})
        for value in (contact.airtable_id, contact.label, raw.get("Record Id", "")):
            if value:
                contact_refs[value.strip().casefold()].add(contact.id)
    # Imported links are evidence to review, not confirmed operational assignments.
    for owner in [*mahs, *users]:
        profile, raw = owner.profile or {}, sources.get(owner.source_row_id, {})
        assigned.update(contact_ids(spoc_ids(profile)))
        assigned.update(contact_ids(profile.get("alert_contact_ids", [])))
        for header in ("Contacts", "SPOC", "Alert contacts"):
            for label in linked_values(raw.get(header, "")):
                imported_references.update(contact_refs.get(label.casefold(), set()))
    supplier_dataset = session.scalar(
        select(StagingDataset.id)
        .where(StagingDataset.source_dataset_name == "IT Suppliers")
        .order_by(StagingDataset.id.desc())
        .limit(1)
    )
    if supplier_dataset:
        for raw in session.scalars(
            select(StagingRow.raw_row_json).where(
                StagingRow.staging_dataset_id == supplier_dataset
            )
        ):
            for header in ("Contacts", "SPOC"):
                for label in linked_values(raw.get(header, "")):
                    imported_references.update(
                        contact_refs.get(label.casefold(), set())
                    )
    for contact in contacts:
        if (
            contact.archived_at
            or (contact.profile or {}).get("registration_pending")
            or contact.id in assigned
        ):
            continue
        raw = sources.get(contact.source_row_id, {})
        if contact.id in imported_references or any(
            linked_values(raw.get(h, ""))
            for h in ("Link MAH", "Link End Users", "Link IT Supplier")
        ):
            add(
                "contact_source_only",
                "Review",
                "Contact",
                contact,
                "Imported relation references exist, but no maintained operational contact assignment is recorded. Review the original links before treating this contact as orphaned.",
            )
        else:
            add(
                "contact_orphan",
                "Review",
                "Contact",
                contact,
                "No maintained assignment or imported relation reference was found. Review before removing any contact.",
            )
    for field, title in (("gln", "GLN"), ("uid", "UID")):
        groups = defaultdict(list)
        for mah in current.values():
            value = re.sub(r"[\s.\-]", "", getattr(mah, field) or "").casefold()
            if value:
                groups[value].append(mah)
        for matches in groups.values():
            if len(matches) > 1:
                for mah in matches:
                    add(
                        "mah_identifier",
                        "Review",
                        "MAH",
                        mah,
                        f"{title} is also recorded on another current MAH; confirm the intended organisation identity.",
                        [
                            (other.name, f"/crm/mahs/{other.id}")
                            for other in matches
                            if other.id != mah.id
                        ],
                    )
    _, unresolved, _ = migration_plan(session)
    user_index = {row.id: row for row in users}
    supplier_index = {row.source_key: row for row in session.scalars(select(CRMITSupplierIdentity))}
    for reference in unresolved:
        cid, kind, target = reference.get("contact_id"), reference["kind"], reference.get("target")
        detail = f"An imported {kind} affiliation is {reference['reason']}; no automatic assignment was made. Review the retained source reference."
        if cid in contact_index:
            add("contact_relation", "Review", "Contact", contact_index[cid], detail)
        elif kind == "mah" and target in mah_index:
            add("contact_relation", "Review", "MAH", mah_index[target], detail)
        elif kind == "end_user" and target in user_index:
            add("contact_relation", "Review", "End User", user_index[target], detail)
        elif kind == "supplier" and target in supplier_index and supplier_index[target].source_row_id:
            add("contact_relation", "Review", "IT Supplier", supplier_index[target], detail)
    return {
        "findings": findings,
        "current_mahs": len(current),
        "eligible_mahs": len(eligible),
    }
