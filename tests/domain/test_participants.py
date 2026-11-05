from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.db.models import ImportMutex, ProcessingRun, StagingDataset, StagingRow
from app.domain.mapping import MappingError
from app.domain.models import (
    LocalLocation,
    LocalOrganisation,
    ParticipantMappingRun,
    ParticipantPublication,
)
from app.domain.participants.mapping import MUTEX, publish_participants
from app.integration.artifacts.storage import utcnow
from app.integration.sources.nmvs.parsing import record_hash
from tests.domain.test_mapping import seed


@pytest.fixture
def participant_sessions(sessions):
    with sessions() as s:
        s.add(ImportMutex(import_key=MUTEX))
        s.commit()
    return sessions


def source(
    sessions, *, orgs=None, locs=None, day=date(2026, 9, 26), omit_locations=False
):
    snapshot, _ = seed(sessions, snapshot_day=day)
    orgs = (
        [
            {
                "Organisation Id": "Org-001",
                "Organisation Name": "Synthetic Pharmacy",
                "Organisation Type": "Pharmacy",
                "Organisation Sub Type": "Healthcare Institution",
                "Organisation Status": "Suspended",
                "Prime Contact": "Private synthetic contact",
                "Prime Contact Email": "private@example.test",
                "Creation Date": "2020-01-01",
                "Registration Date": "2020-01-02",
                "Expiry Date": "",
            }
        ]
        if orgs is None
        else orgs
    )
    locs = (
        [
            {
                "Organisation Id": "Org-001",
                "Location Id": "Loc-001",
                "Location Name": "Synthetic location",
                "Organisation Name": "Original location-side organisation name",
                "Location Status": "Active",
                "Equipment Count": "2",
                "City": "Synthetic City",
                "Postal Code": "0123",
                "Address": "Line 1\nLine 2",
                "Legitimacy Information": "Source assertion only",
                "Creation Date": "2020-01-02",
            }
        ]
        if locs is None
        else locs
    )
    with sessions() as s:
        run = s.get(ProcessingRun, snapshot)
        for order, (name, rows) in enumerate(
            [("Organisations", orgs)]
            + ([] if omit_locations else [("Locations", locs)]),
            3,
        ):
            d = StagingDataset(
                processing_run_id=run.id,
                artifact_id=run.artifact_id,
                source_dataset_name=name,
                section_order=order,
                source_headers=list(rows[0]) if rows else [],
                row_count=len(rows),
                extraction_status="extracted",
                created_at=utcnow(),
            )
            s.add(d)
            s.flush()
            for number, row in enumerate(rows, 1):
                s.add(
                    StagingRow(
                        staging_dataset_id=d.id,
                        source_row_number=number,
                        source_record_hash=record_hash(row),
                        raw_row_json=row,
                        created_at=utcnow(),
                    )
                )
        s.commit()
    return snapshot


def counts(sessions):
    with sessions() as s:
        return [
            s.scalar(select(func.count()).select_from(model))
            for model in (LocalOrganisation, LocalLocation, ParticipantMappingRun)
        ]


def test_participants_links_repeat_stable_ids_original_values_and_separate_statuses(
    participant_sessions,
):
    factory = participant_sessions
    identifier = source(factory)
    run = publish_participants(factory, identifier, "synthetic")
    before = counts(factory)
    assert publish_participants(factory, identifier, "synthetic").id == run.id
    assert counts(factory) == before == [1, 1, 1]
    with factory() as s:
        org = s.scalar(select(LocalOrganisation))
        location = s.scalar(select(LocalLocation))
        assert location.organisation_id == org.id
        assert (
            org.organisation_status == "Suspended"
            and location.location_status == "Active"
        )
        assert (
            location.postal_code == "0123" and org.source_organisation_id == "Org-001"
        )
        assert org.evidence["Prime Contact Email"] == "private@example.test"
        assert (
            location.evidence["Organisation Name"]
            == "Original location-side organisation name"
        )


def test_orphan_and_missing_parent_id_are_retained(participant_sessions):
    factory = participant_sessions
    identifier = source(
        factory,
        orgs=[],
        locs=[
            {
                "Organisation Id": "Absent",
                "Location Id": "Orphan",
                "Location Status": "Deleted",
            },
            {
                "Organisation Id": "",
                "Location Id": "NoParent",
                "Location Status": "Active",
            },
        ],
    )
    run = publish_participants(factory, identifier, "synthetic")
    assert run.statistics["unlinked_locations"] == 2
    with factory() as s:
        rows = s.scalars(select(LocalLocation)).all()
        assert all(r.organisation_id is None for r in rows)
        assert {r.organisation_link_status for r in rows} == {
            "organisation_not_in_snapshot",
            "missing_organisation_id",
        }
        assert len(rows) == 2


def test_reassignment_does_not_change_location_identity(participant_sessions):
    factory = participant_sessions
    publish_participants(factory, source(factory), "synthetic")
    with factory() as s:
        original = s.scalar(select(LocalLocation.id))
    other = source(
        factory,
        day=date(2026, 9, 27),
        orgs=[{"Organisation Id": "NewOrg", "Organisation Name": "New parent"}],
        locs=[
            {
                "Location Id": "Loc-001",
                "Organisation Id": "NewOrg",
                "Location Status": "Deleted",
            }
        ],
    )
    publish_participants(factory, other, "synthetic")
    with factory() as s:
        location = s.scalar(select(LocalLocation))
        assert location.id == original and location.location_status == "Deleted"
        assert (
            s.get(LocalOrganisation, location.organisation_id).source_organisation_id
            == "NewOrg"
        )
        old = s.scalar(
            select(LocalOrganisation).where(
                LocalOrganisation.source_organisation_id == "Org-001"
            )
        )
        assert old.is_observed == 0


def test_disappearance_keeps_records_without_inventing_deletion(participant_sessions):
    factory = participant_sessions
    publish_participants(factory, source(factory), "synthetic")
    publish_participants(
        factory, source(factory, day=date(2026, 9, 27), orgs=[], locs=[]), "synthetic"
    )
    with factory() as s:
        assert s.scalar(select(LocalOrganisation)).is_observed == 0
        location = s.scalar(select(LocalLocation))
        assert location.is_observed == 0 and location.location_status == "Active"


def test_duplicate_key_failure_preserves_previous_publication(participant_sessions):
    factory = participant_sessions
    first = publish_participants(factory, source(factory), "synthetic")
    duplicated = source(
        factory,
        day=date(2026, 9, 27),
        orgs=[{"Organisation Id": "Same"}, {"Organisation Id": "Same"}],
    )
    with pytest.raises(MappingError):
        publish_participants(factory, duplicated, "synthetic")
    with factory() as s:
        assert s.get(ParticipantPublication, "participants").mapping_run_id == first.id
        assert s.scalar(select(LocalOrganisation)).is_observed == 1
        assert (
            s.scalar(
                select(ParticipantMappingRun).order_by(ParticipantMappingRun.id.desc())
            ).status
            == "failed"
        )


def test_partial_write_is_rolled_back_and_error_is_sanitized(participant_sessions):
    from sqlalchemy import event

    factory = participant_sessions
    first = publish_participants(factory, source(factory), "synthetic")
    identifier = source(factory, day=date(2026, 9, 27))
    engine = factory.kw["bind"]

    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO local_locations"):
            raise RuntimeError("private@example.test")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(MappingError) as failure:
            publish_participants(factory, identifier, "synthetic")
        assert "private@" not in str(failure.value)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with factory() as s:
        assert s.scalar(select(LocalOrganisation)).last_participant_run_id == first.id
        assert s.get(ParticipantPublication, "participants").mapping_run_id == first.id


def test_missing_dataset_stale_and_same_day_inputs_refused(participant_sessions):
    factory = participant_sessions
    first = publish_participants(factory, source(factory), "synthetic")
    for day in [date(2026, 9, 25), date(2026, 9, 26)]:
        with pytest.raises(MappingError):
            publish_participants(factory, source(factory, day=day), "synthetic")
    with pytest.raises(MappingError):
        publish_participants(
            factory,
            source(factory, day=date(2026, 9, 27), omit_locations=True),
            "synthetic",
        )
    with factory() as s:
        assert s.get(ParticipantPublication, "participants").mapping_run_id == first.id


def test_source_ids_remain_case_sensitive(participant_sessions):
    factory = participant_sessions
    run = publish_participants(
        factory,
        source(
            factory,
            orgs=[{"Organisation Id": "Org"}, {"Organisation Id": "org"}],
            locs=[],
        ),
        "synthetic",
    )
    assert run.statistics["organisations"] == 2
