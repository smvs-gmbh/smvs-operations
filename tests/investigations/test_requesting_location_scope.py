from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.alert_desk.test_workspace import create_workspace, fixture_database
from app.domain.investigations import pilot
from app.domain.investigations.pilot_api import create_app
from app.domain.mapping import key
from app.domain.models import AlertDeskAccess, LocalLocation, NMVSException


def test_end_user_scope_requires_current_requesting_location_for_reads_and_writes(tmp_path):
    engine, factory = fixture_database(tmp_path / "scope.db")
    create_workspace(factory)
    secret = "requesting-location-test-" * 3
    session_token = "e" * 43
    variants = {
        "own-imt": ({"is_intermarket": 1}, True),
        "missing-location": ({"source_location_id": None, "last_update_location_id": "fixture-location"}, False),
        "empty-location": ({"source_location_id": ""}, False),
        "other-requester": ({"source_location_id": "another-location", "last_update_location_id": "fixture-location"}, False),
        "foreign-market": ({"source_market": "DE"}, False),
        "wrong-organisation": ({"organisation_id": "different-org"}, False),
        "location-only": ({"organisation_id": None}, True),
        "second-own-location": ({"source_location_id": "second-own-location"}, True),
        "other-namespace": ({"source_namespace": "different-source"}, False),
    }
    ids = {}
    with factory.begin() as s:
        grant = s.scalar(select(AlertDeskAccess).where(AlertDeskAccess.role == "end_user"))
        grant.session_hash = pilot.digest(session_token)
        original = s.scalar(select(NMVSException).where(NMVSException.error_code == "A3"))
        columns = {c.key: getattr(original, c.key) for c in NMVSException.__table__.columns if c.key != "id"}
        location = s.scalar(select(LocalLocation).where(LocalLocation.source_location_id == "fixture-location"))
        loc_columns = {c.key: getattr(location, c.key) for c in LocalLocation.__table__.columns if c.key != "id"}
        second = LocalLocation(**{**loc_columns, "source_key": key("second-location"), "source_location_id": "second-own-location"})
        s.add(second)
        for label, (changes, _) in variants.items():
            row = NMVSException(**{**columns, **changes, "alert_key": key("requesting-location", label), "unique_alert_id": label})
            s.add(row)
            s.flush()
            ids[label] = row.id
    headers = {"Authorization": "Bearer " + secret, "X-Case-Session": session_token}
    try:
        with TestClient(create_app(factory, secret), client=("127.0.0.1", 1234)) as client:
            listing = client.get("/access/alerts", headers=headers)
            assert listing.status_code == 200
            for label, (_, visible) in variants.items():
                identifier = ids[label]
                assert any(r["id"] == identifier for r in listing.json()["rows"]) == visible
                detail = client.get(f"/access/alerts/{identifier}", headers=headers)
                assert detail.status_code == (200 if visible else 404)
                templates = client.get(f"/access/alerts/{identifier}/comment-templates", headers=headers)
                assert templates.status_code == (200 if visible else 404)
                if not visible:
                    body = {"publication": identifier, "submission_key": str(uuid4()), "basis": columns["payload_hash"], "comparison": "not_checked", "finding": "investigating"}
                    assert client.post(f"/access/alerts/{identifier}/findings", headers=headers, json=body).status_code == 404
            # Removing a location assignment immediately invalidates an open case.
            with factory.begin() as s:
                loc = s.scalar(select(LocalLocation).where(LocalLocation.source_location_id == "second-own-location"))
                loc.is_observed = 0
            assert client.get(f"/access/alerts/{ids['second-own-location']}", headers=headers).status_code == 404
            # The reviewed foreign export cohort seeded in the fixture grants no access.
            assert client.get("/access/alerts/4", headers=headers).status_code == 404
    finally:
        engine.dispose()
