"""One contact affiliation read model, with explicit membership and independent roles.

General membership never grants SPOC/Alert permissions. Existing guarded role
assignments remain authoritative for recipients and are projected into this model.
"""

import argparse
import json
from collections import defaultdict

from sqlalchemy import select

from app.core.db.models import StagingRow
from app.domain.crm.contact_assignments import spoc_ids
from app.domain.crm.imports import linked_values, staged_crm_export
from app.domain.models import (
    CRMContact,
    CRMContactLinkEvent,
    CRMContactOrganisationLink,
    CRMEndUser,
    CRMITSupplierIdentity,
    CRMMah,
)
from app.integration.artifacts.storage import utcnow

TARGETS = {
    "mah": (CRMMah, "mah_id", "MAH", "mahs"),
    "end_user": (CRMEndUser, "end_user_id", "End User", "end-users"),
    "supplier": (CRMITSupplierIdentity, "supplier_id", "IT Supplier", "it-suppliers"),
}


def valid_ids(values):
    return (
        {v for v in values if type(v) is int and v > 0}
        if isinstance(values, (list, tuple))
        else set()
    )


def target_of(link):
    for kind, (_, column, _, _) in TARGETS.items():
        value = getattr(link, column)
        if value is not None:
            return kind, value
    raise ValueError("Contact link has no organisation.")


def target_catalogue(session):
    result = {}
    for kind, (model, _, label, directory) in TARGETS.items():
        for row in session.scalars(select(model).order_by(model.id)):
            roles = defaultdict(list)
            if kind != "supplier":
                for cid in valid_ids(spoc_ids(row.profile)):
                    roles[cid].append("SPOC")
                for cid in valid_ids((row.profile or {}).get("alert_contact_ids", [])):
                    roles[cid].append("Alert contact")
            available = (
                (row.is_current and row.source_row_id is not None)
                if kind == "supplier"
                else not row.archived_at
            )
            identifier = row.source_row_id if kind == "supplier" else row.id
            result[(kind, row.id)] = {
                "kind": kind,
                "id": row.id,
                "token": f"{kind}:{row.id}",
                "type": label,
                "name": row.name,
                "url": f"/crm/{directory}/{identifier}" if identifier else None,
                "available": available,
                "role_contacts": roles,
                "record": row,
            }
    return result


def affiliations(session, identifiers=None):
    targets = target_catalogue(session)
    result = defaultdict(dict)
    query = select(CRMContactOrganisationLink).where(
        CRMContactOrganisationLink.is_active.is_(True)
    )
    if identifiers is not None:
        query = query.where(CRMContactOrganisationLink.contact_id.in_(identifiers))
    for link in session.scalars(query):
        key = target_of(link)
        target = targets.get(key)
        if not target:
            continue
        roles = target["role_contacts"].get(link.contact_id, [])
        if link.supplier_spoc and key[0] == "supplier":
            roles = ["SPOC"]
        result[link.contact_id][key] = {
            **target,
            "roles": roles or ["Contact"],
            "origin": link.origin,
        }
    for key, target in targets.items():
        for cid, roles in target["role_contacts"].items():
            if identifiers is None or cid in identifiers:
                result[cid][key] = {
                    **target,
                    "roles": roles,
                    "origin": "Role assignment",
                }
    return {
        cid: sorted(
            items.values(), key=lambda v: (v["name"].casefold(), v["type"], v["id"])
        )
        for cid, items in result.items()
    }


def event(session, contact_id, kind, target_id, action, actor=None):
    session.add(
        CRMContactLinkEvent(
            contact_id=contact_id,
            target_type=kind,
            target_id=target_id,
            action=action,
            actor_user_id=actor,
            occurred_at=utcnow(),
        )
    )


def set_affiliations(session, contact, tokens, actor=None):
    """Version-check/lock the Contact before calling. Inactive rows are reimport tombstones."""
    if (
        not isinstance(tokens, list)
        or len(tokens) > 300
        or any(not isinstance(t, str) for t in tokens)
    ):
        raise ValueError("Select valid organisation assignments.")
    targets = target_catalogue(session)
    by_token = {target["token"]: key for key, target in targets.items()}
    if any(token not in by_token for token in tokens):
        raise ValueError("Select an existing organisation.")
    selected = {by_token[t] for t in tokens}
    existing = {
        target_of(link): link
        for link in session.scalars(
            select(CRMContactOrganisationLink)
            .where(CRMContactOrganisationLink.contact_id == contact.id)
            .with_for_update()
        )
    }
    locked = {
        key for key, target in targets.items() if contact.id in target["role_contacts"]
    }
    selected |= locked  # General affiliation editing cannot remove an operational role.
    for key in selected:
        link = existing.get(key)
        if (
            not targets[key]["available"]
            and not (link and link.is_active)
            and key not in locked
        ):
            raise ValueError("Restore the organisation before assigning a new contact.")
    for key in selected | set(existing):
        kind, identifier = key
        link = existing.get(key)
        active = key in selected
        if (
            active
            and not targets[key]["available"]
            and not (link and link.is_active)
            and key not in locked
        ):
            raise ValueError("Restore the organisation before assigning a new contact.")
        if link is None:
            _, column, _, _ = TARGETS[kind]
            link = CRMContactOrganisationLink(
                contact_id=contact.id,
                **{column: identifier},
                is_active=active,
                origin="manual",
                supplier_spoc=False,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            session.add(link)
            event(session, contact.id, kind, identifier, "Assigned", actor)
        elif link.is_active != active:
            link.is_active = active
            link.origin = "manual"
            link.updated_at = utcnow()
            event(
                session,
                contact.id,
                kind,
                identifier,
                "Assigned" if active else "Unassigned",
                actor,
            )


def migration_plan(session):
    """Read-only plan. Exact identifiers/unique export labels only; no fuzzy merges."""
    contacts = list(session.scalars(select(CRMContact)))
    owners = {
        kind: list(session.scalars(select(model)))
        for kind, model in (("mah", CRMMah), ("end_user", CRMEndUser))
    }
    source_ids = {
        r.source_row_id
        for r in [*contacts, *owners["mah"], *owners["end_user"]]
        if r.source_row_id
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
    export = staged_crm_export(session, "IT Suppliers")
    suppliers = export[3] if export else []
    indices = {kind: defaultdict(set) for kind in TARGETS}
    contact_index = defaultdict(set)
    for contact in contacts:
        raw = sources.get(contact.source_row_id) or {}
        for key in (contact.airtable_id, raw.get("Record Id"), contact.label):
            if key:
                contact_index[key.strip()].add(contact.id)
    for kind, rows in owners.items():
        for row in rows:
            raw = sources.get(row.source_row_id) or {}
            for key in (
                getattr(row, "airtable_id", None),
                raw.get("RECORD_ID"),
                raw.get("Record Id"),
            ):
                if key:
                    indices[kind][key.strip()].add(row.id)
    supplier_rows = {}
    for row in suppliers:
        key = row.raw_row_json["Record Id"].strip()
        if key in supplier_rows:
            raise ValueError(
                "Duplicate IT supplier source identity; resolve before migration."
            )
        supplier_rows[key] = row
        indices["supplier"][key].add(key)
    proposed = {}
    unresolved = []

    def add_ref(cid, kind, reference, source_row, supplier_spoc=False):
        candidates = indices[kind].get(reference, set())
        if len(candidates) != 1:
            unresolved.append(
                {
                    "contact_id": cid,
                    "kind": kind,
                    "source_row_id": source_row,
                    "reason": "ambiguous" if candidates else "missing",
                }
            )
            return
        target = next(iter(candidates))
        key = (cid, kind, target)
        proposed[key] = (
            source_row,
            supplier_spoc or proposed.get(key, (None, False))[1],
        )

    for contact in contacts:
        raw = sources.get(contact.source_row_id) or {}
        for kind, header in (
            ("mah", "Link MAH"),
            ("end_user", "Link End Users"),
            ("supplier", "Link IT Supplier"),
        ):
            for reference in linked_values(raw.get(header, "")):
                add_ref(contact.id, kind, reference, contact.source_row_id)
    for kind, rows in [*owners.items(), ("supplier", suppliers)]:
        for row in rows:
            raw = (
                row.raw_row_json
                if kind == "supplier"
                else sources.get(row.source_row_id) or {}
            )
            identity = raw["Record Id"].strip() if kind == "supplier" else row.id
            source_id = row.id if kind == "supplier" else row.source_row_id
            for header in ("Contacts", "SPOC", "Alert contacts"):
                for reference in linked_values(raw.get(header, "")):
                    candidates = contact_index.get(reference, set())
                    if len(candidates) != 1:
                        unresolved.append(
                            {
                                "kind": kind,
                                "target": identity,
                                "source_row_id": source_id,
                                "reason": "ambiguous" if candidates else "missing",
                            }
                        )
                        continue
                    cid = next(iter(candidates))
                    key = (cid, kind, identity)
                    proposed[key] = (
                        source_id,
                        (kind == "supplier" and header == "SPOC")
                        or proposed.get(key, (None, False))[1],
                    )
    return proposed, unresolved, supplier_rows


def migrate_affiliations(session, *, apply=False):
    proposed, unresolved, supplier_rows = migration_plan(session)
    existing_suppliers = {
        r.source_key: r
        for r in session.scalars(
            select(CRMITSupplierIdentity).with_for_update()
            if apply
            else select(CRMITSupplierIdentity)
        )
    }
    links = {
        (r.contact_id, *target_of(r)): r
        for r in session.scalars(select(CRMContactOrganisationLink))
    }
    added = skipped = 0
    if apply:
        for key, row in supplier_rows.items():
            identity = existing_suppliers.get(key)
            if identity is None:
                identity = CRMITSupplierIdentity(
                    source_key=key,
                    name=row.raw_row_json["IT Supplier Name"],
                    source_row_id=row.id,
                    is_current=True,
                )
                session.add(identity)
                session.flush()
                existing_suppliers[key] = identity
            else:
                identity.source_row_id = row.id
                identity.name = row.raw_row_json["IT Supplier Name"]
                identity.is_current = True
        for key, identity in existing_suppliers.items():
            if key not in supplier_rows:
                identity.is_current = False
    for (cid, kind, identifier), (source_id, spoc) in proposed.items():
        target_id = (
            existing_suppliers[identifier].id
            if kind == "supplier" and identifier in existing_suppliers
            else identifier
        )
        if (cid, kind, target_id) in links:
            skipped += 1
            continue
        added += 1
        if apply:
            _, column, _, _ = TARGETS[kind]
            session.add(
                CRMContactOrganisationLink(
                    contact_id=cid,
                    **{column: target_id},
                    is_active=True,
                    supplier_spoc=spoc,
                    origin="airtable",
                    source_row_id=source_id,
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
            event(session, cid, kind, target_id, "Imported affiliation")
    return {
        "proposed": len(proposed),
        "new_links": added,
        "existing_decisions_preserved": skipped,
        "unresolved": unresolved,
        "supplier_identities": len(supplier_rows),
    }


def main():
    from app.core.db.session import SessionFactory

    parser = argparse.ArgumentParser(
        description="Review or migrate CRM contact affiliations; default is read-only."
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionFactory() as session:
        result = migrate_affiliations(session, apply=args.apply)
        if args.apply:
            session.commit()
        else:
            session.rollback()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
