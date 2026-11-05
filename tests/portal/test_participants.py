import pytest

from app.core.db.models import ImportMutex
from app.domain.participants.mapping import MUTEX, publish_participants
from app.portal.participant_routes import router
from tests.domain.test_participants import source


@pytest.fixture
def participants_portal(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory() as s:
        s.add(ImportMutex(import_key=MUTEX))
        s.commit()
    return client, factory


def test_organisation_list_filters_detail_and_independent_states(participants_portal):
    client, factory = participants_portal
    publish_participants(factory, source(factory), "synthetic")
    page = client.get("/organisations")
    assert page.status_code == 200 and "Synthetic Pharmacy" in page.text
    assert "private@example.test" not in page.text
    assert (
        "No matching organisations" in client.get("/organisations?status=Active").text
    )
    assert (
        "Synthetic Pharmacy"
        in client.get("/organisations?status=Suspended&type=Pharmacy").text
    )
    assert "No matching organisations" in client.get("/organisations?q=%25").text
    detail = client.get("/organisations/1")
    assert detail.status_code == 200 and "Synthetic location" in detail.text
    assert "Suspended" in detail.text and "Active" in detail.text
    assert client.get("/organisations/999").status_code == 404
    assert "SAI export" not in page.text


def test_original_values_and_location_detail(participants_portal):
    client, factory = participants_portal
    publish_participants(factory, source(factory), "synthetic")
    original = client.get("/organisations/1/source")
    assert original.status_code == 200 and "private@example.test" in original.text
    assert "Prime Contact Email" in original.text
    assert "Product Name und MAH Name" not in original.text
    assert "Synthetic location" in client.get("/locations?q=Synthetic").text
    assert "No Locations" in client.get("/locations?status=Deleted").text
    detail = client.get("/locations/1")
    assert (
        detail.status_code == 200
        and "Synthetic Pharmacy" in detail.text
        and "0123" in detail.text
    )
    raw = client.get("/locations/1/source")
    assert (
        raw.status_code == 200
        and "Original location-side organisation name" in raw.text
    )
    assert client.get("/locations/999").status_code == 404


def test_unmatched_location_is_visible_and_searchable_without_fake_parent(
    participants_portal,
):
    client, factory = participants_portal
    identifier = source(
        factory,
        orgs=[],
        locs=[
            {
                "Location Id": "Orphan-001",
                "Organisation Id": "Unknown",
                "Location Name": "Standalone",
                "Location Status": "Deleted",
            }
        ],
    )
    publish_participants(factory, identifier, "synthetic")
    page = client.get("/locations?q=Unknown")
    assert (
        page.status_code == 200
        and "Standalone" in page.text
        and "Organisation not linked" in page.text
    )
    detail = client.get("/locations/1")
    assert (
        detail.status_code == 200
        and "Not linked in the selected snapshot" in detail.text
    )


def test_source_pages_escape_contact_values_and_survive_staging_expiry(
    participants_portal,
):
    from sqlalchemy import select

    from app.core.db.models import StagingRow
    from app.domain.models import LocalOrganisation

    client, factory = participants_portal
    identifier = source(
        factory,
        orgs=[
            {
                "Organisation Id": "X",
                "Organisation Name": "<script>alert(1)</script>",
                "Prime Contact": "<img src=x onerror=alert(1)>",
            }
        ],
        locs=[],
    )
    publish_participants(factory, identifier, "synthetic")
    with factory() as s:
        org = s.scalar(select(LocalOrganisation))
        row = s.get(StagingRow, org.source_row_id)
        org.source_row_id = None
        s.flush()
        s.delete(row)
        s.commit()
    page = client.get("/organisations/1/source")
    assert (
        page.status_code == 200
        and "&lt;script&gt;" in page.text
        and "&lt;img" in page.text
    )
    assert "<script>" not in page.text and "<img src=x" not in page.text
    assert "Retained source values" in page.text


def test_empty_state_pagination_and_invalid_parameters(participants_portal):
    client, factory = participants_portal
    assert "No organisation/location dataset" in client.get("/organisations").text
    orgs = [
        {"Organisation Id": f"{i:03d}", "Organisation Name": f"Organisation {i:03d}"}
        for i in range(45)
    ]
    publish_participants(factory, source(factory, orgs=orgs, locs=[]), "synthetic")
    assert "Page 1 / 2" in client.get("/organisations").text
    assert "Page 2 / 2" in client.get("/organisations?page=2").text
    assert client.get("/organisations?page=0").status_code == 422
    assert client.get("/locations?page=0").status_code == 422
