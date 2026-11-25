"""Match and seed CRM End Users from the staged Airtable export."""

from collections import Counter, defaultdict

from sqlalchemy import false, select

from app.core.db.models import StagingRow
from app.domain.crm.contact_assignments import has_spoc_assignment
from app.domain.crm.imports import linked_values, staged_crm_export
from app.domain.models import (
    CRMContact,
    CRMEndUser,
    LocalOrganisation,
    ParticipantPublication,
)


def current_organisations(session):
    publication = session.get(ParticipantPublication, "participants")
    if not publication:
        return None, select(LocalOrganisation).where(false())
    return publication, select(LocalOrganisation).where(
        LocalOrganisation.source_namespace == publication.source_namespace,
        LocalOrganisation.is_observed == 1,
        LocalOrganisation.last_participant_run_id == publication.mapping_run_id,
    )


def match_end_users(session, staged_rows):
    rows = [row.raw_row_json for row in staged_rows]
    publication, statement = current_organisations(session)
    organisations = defaultdict(list)
    for organisation in session.scalars(statement):
        organisations[(organisation.organisation_name or "").strip()].append(
            organisation
        )
    record_ids = Counter(row["Record Id"].strip() for row in rows)
    names = Counter(row["End User Name"].strip() for row in rows)
    results = []
    for staged, row in zip(staged_rows, rows, strict=True):
        label = row["Record Id"].strip()
        name = row["End User Name"].strip()
        candidates = organisations[name]
        if label != name:
            status = "Source names differ"
        elif record_ids[label] > 1 or names[name] > 1 or len(candidates) > 1:
            status = "Ambiguous"
        elif not publication:
            status = "Snapshot unavailable"
        elif not candidates:
            status = "No exact match"
        else:
            status = "Exact match"
        results.append(
            (staged.id, row, status, candidates[0] if status == "Exact match" else None)
        )
    return publication, results


def seed_end_users(session):
    export = staged_crm_export(session, "End Users")
    if not export:
        raise ValueError("Stage an End Users export first.")
    _, _, _, rows = export
    _, matches = match_end_users(session, rows)
    existing = {
        user.source_row_id
        for user in session.scalars(select(CRMEndUser).with_for_update())
        if user.source_row_id is not None
    }
    occupied = set(session.scalars(select(CRMEndUser.organisation_id)))
    # Reimporting a changed export must not create a new End User for every new
    # staging-row ID, nor overwrite manually maintained CRM values.
    previous = defaultdict(list)
    for owner, raw_source in session.execute(select(CRMEndUser, StagingRow.raw_row_json).join(StagingRow, CRMEndUser.source_row_id == StagingRow.id)):
        source = raw_source or {}
        key = (source.get("RECORD_ID") or source.get("Record Id") or "").strip()
        if key:
            previous[key].append(owner.id)
    incoming = Counter((raw.get("RECORD_ID") or raw.get("Record Id") or "").strip() for _, raw, _, _ in matches)
    if not set(previous).issubset(incoming):
        raise ValueError("Review changed or missing source identities before importing this End Users export; no CRM record was changed.")
    for row_id, raw, _, _ in matches:
        key = (raw.get("RECORD_ID") or raw.get("Record Id") or "").strip()
        if row_id not in existing and key in previous and (len(previous[key]) != 1 or incoming[key] != 1):
            raise ValueError("An End User source identity is ambiguous. Review before reimporting; no CRM record was changed.")
    created = linked = 0
    for row_id, raw, _, candidate in matches:
        source_key = (raw.get("RECORD_ID") or raw.get("Record Id") or "").strip()
        if row_id in existing or source_key in previous:
            continue
        organisation_id = (
            candidate.id if candidate and candidate.id not in occupied else None
        )
        session.add(
            CRMEndUser(
                name=raw["End User Name"].strip() or raw["Record Id"].strip(),
                source_row_id=row_id,
                organisation_id=organisation_id,
                link_origin="exact" if organisation_id else None,
            )
        )
        occupied.add(organisation_id)
        created += 1
        linked += organisation_id is not None
    from app.domain.crm.organisation_links import migrate_affiliations
    migrate_affiliations(session, apply=True)
    return created, linked


def contact_reference_index(session):
    by_id = {}
    by_label = defaultdict(list)
    for contact, raw in session.execute(
        select(CRMContact, StagingRow.raw_row_json)
        .outerjoin(StagingRow, CRMContact.source_row_id == StagingRow.id)
        .where(
            CRMContact.archived_at.is_(None),
            CRMContact.profile['registration_pending'].as_boolean().is_not(True),
        )
    ):
        by_id[contact.airtable_id] = contact.id
        label = (raw or {}).get("Record Id", contact.label).strip()
        by_label[label].append(contact.id)
    return by_id, by_label


def resolve_end_user_contacts(source, index):
    by_id, by_label = index
    assignments = {}
    pending = []
    for header, field in (
        ("SPOC", "spoc_ids"),
        ("Alert contacts", "alert_contact_ids"),
    ):
        references = list(dict.fromkeys(linked_values(source.get(header, ""))))
        matches = []
        for reference in references:
            candidates = (
                [by_id[reference]]
                if reference in by_id
                else by_label.get(reference, [])
            )
            if len(candidates) == 1:
                matches.append(candidates[0])
            else:
                reason = "Ambiguous match" if candidates else "No matching contact"
                pending.append(f"{header} · {reason} · {reference}")
        if matches:
            assignments[field] = list(dict.fromkeys(matches))
    return assignments, pending


def seed_end_user_contacts(session):
    index = contact_reference_index(session)
    changed = Counter()
    for user, source in session.execute(
        select(CRMEndUser, StagingRow.raw_row_json)
        .join(StagingRow, CRMEndUser.source_row_id == StagingRow.id)
        .where(CRMEndUser.archived_at.is_(None))
        .with_for_update()
    ):
        profile = user.profile or {}
        assignments, _ = resolve_end_user_contacts(source, index)
        missing = {
            field: value
            for field, value in assignments.items()
            if field not in profile
            and (field != "spoc_ids" or not has_spoc_assignment(profile))
        }
        if missing:
            user.profile = profile | missing
            changed.update(missing.keys())
    return changed


def main():
    from app.core.db.session import SessionFactory

    with SessionFactory() as session:
        created, linked = seed_end_users(session)
        contacts = seed_end_user_contacts(session)
        session.commit()
    print(f"{created} End Users created; {linked} linked to NMVS.")
    print(
        f"{contacts['spoc_ids']} SPOC and {contacts['alert_contact_ids']} Alert contact groups assigned."
    )


if __name__ == "__main__":
    main()
