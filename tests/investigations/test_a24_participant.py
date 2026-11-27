import re
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.alert_desk.schema import Findings
from app.alert_desk.test_workspace import ORIGIN, create_workspace, fixture_database
from app.domain.models import AlertDeskEvent, NMVSException


def test_own_a24_findings_comments_capa_and_foreign_requester_exclusion(tmp_path):
    engine, factory = fixture_database(tmp_path / "a24.db")
    try:
        with TestClient(create_workspace(factory), base_url=ORIGIN, client=("127.0.0.1", 1234)) as client:
            path = "/cases/6/end_user"
            page = client.get(path)
            assert page.status_code == 200 and "Your investigation" in page.text
            assert 'name="comparison"' not in page.text
            assert 'name="batch_uploaded"' not in page.text
            assert "No batch reference" not in page.text
            assert "does not change the pack state" in page.text
            hidden = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', page.text))
            body = {"publication": 6, "basis": hidden["basis"], "submission_key": str(uuid4()), "finding": "investigating", "comment": "Reviewing our Supply request."}
            assert client.post(path + "/findings", json=body, headers={"Origin": ORIGIN}).status_code == 200
            assert body["comment"] in client.get(path).text
            own = {**body, "submission_key": str(uuid4()), "finding": "procedural"}
            assert client.post(path + "/findings", json=own, headers={"Origin": ORIGIN}).status_code == 422
            own["capa"] = "planned"
            assert client.post(path + "/findings", json=own, headers={"Origin": ORIGIN}).status_code == 200
            assert client.post(path + "/findings", json=own, headers={"Origin": ORIGIN}).status_code == 200
            with factory() as s:
                events = s.scalars(select(AlertDeskEvent).where(AlertDeskEvent.kind == "Findings submitted")).all()
                assert len(events) == 2
                assert events[-1].data["capa"] == "planned"
                assert s.get(NMVSException, 6).source_location_id == "fixture-location"
            for change in [{"comparison": "yes"}, {"batch_uploaded": "yes"}, {"pack_on_hold": True}, {"batch_revision": "a" * 64}]:
                assert client.post(path + "/findings", json={**own, **change, "submission_key": str(uuid4())}, headers={"Origin": ORIGIN}).status_code == 422
            # The foreign requester stays hidden even though an earlier action
            # mentions the End User's own Location.
            assert client.get("/cases/7/end_user").status_code == 404
            assert client.get("/cases/7/end_user/comment-templates").status_code == 404
            assert client.post("/cases/7/end_user/findings", json={**body, "publication": 7}, headers={"Origin": ORIGIN}).status_code == 404
            assert "Your investigation" not in client.get("/cases/6/mah").text
            assert client.post("/cases/6/mah/findings", json=body, headers={"Origin": ORIGIN}).status_code == 404
            assert not Findings(**body).matches_audience("mah", "A24")
            # Verified ownership comes from the server's current Location scope,
            # including records where the source omitted an Organisation ID.
            with factory.begin() as s:
                s.get(NMVSException, 6).organisation_id = None
            assert "Your investigation" in client.get(path).text
            assert client.post(path + "/findings", json={**body, "submission_key": str(uuid4())}, headers={"Origin": ORIGIN}).status_code == 200
    finally:
        engine.dispose()


def test_mah_a24_information_self_report_and_scoped_request(tmp_path):
    from datetime import timedelta

    from app.domain.investigations import pilot, responses
    from app.domain.models import AlertDeskResponseRequest, CRMMah, PortalUser
    from app.portal.exception_queries import enriched

    engine, factory = fixture_database(tmp_path / "mah-a24.db")
    try:
        with TestClient(create_workspace(factory), base_url=ORIGIN, client=("127.0.0.1", 1234)) as client:
            path = "/cases/6/mah"
            page = client.get(path)
            assert page.status_code == 404
            with factory() as s:
                basis = s.get(NMVSException, 6).payload_hash
            body = {"publication": 6, "basis": basis, "submission_key": str(uuid4()), "finding": "investigating", "comment": "Checking our earlier transactions."}
            endpoint = path + "/findings"
            assert client.post(endpoint, json=body, headers={"Origin": ORIGIN}).status_code == 404
            # A specific current-source/current-MAH request enables the flow.
            with factory.begin() as s:
                user = PortalUser(email="staff@example.test",handle="a24-staff",is_admin=1,is_nmvo=1)
                s.add(user);s.flush()
                record=s.get(NMVSException,6)
                crm, _recipients, issue = responses.recipient_scope(s,record,"mah",enriched(s,[record])[0])
                assert crm is not None and "Findings unavailable" not in issue
                request=AlertDeskResponseRequest(exception_id=6,role="mah",crm_organisation_id=crm.id+100,source_version=record.payload_hash,after_event_id=0,actor_id=user.id,requested_at=pilot.now(),due_on=(pilot.now()+timedelta(days=3)).date())
                s.add(request);s.flush();request_id=request.id;crm_id=crm.id
            assert client.get(path).status_code == 404
            assert client.post(endpoint,json=body,headers={"Origin":ORIGIN}).status_code==404
            with factory.begin() as s:s.get(AlertDeskResponseRequest,request_id).crm_organisation_id=crm_id
            assert "SMVS has requested an investigation" in client.get(path).text
            assert client.post(endpoint,json=body,headers={"Origin":ORIGIN}).status_code==200
            with factory.begin() as s:s.get(AlertDeskResponseRequest,request_id).source_version="0"*64
            assert client.post(endpoint,json={**body,"submission_key":str(uuid4())},headers={"Origin":ORIGIN}).status_code==404
            # An explicit own-side declaration is accepted and retained separately
            # from the eventual root-cause finding and NMVO decision.
            own={**body,"submission_key":str(uuid4()),"own_cause":True}
            assert client.post(endpoint,json=own,headers={"Origin":ORIGIN}).status_code==404
            with factory.begin() as s:s.get(AlertDeskResponseRequest,request_id).source_version=basis
            assert client.post(endpoint,json=own,headers={"Origin":ORIGIN}).status_code==200
            with factory.begin() as s:s.get(AlertDeskResponseRequest,request_id).source_version="0"*64
            assert "No investigation requested." not in client.get(path).text
            own={**own,"submission_key":str(uuid4()),"finding":"other"}
            assert client.post(endpoint,json=own,headers={"Origin":ORIGIN}).status_code==422
            own["capa"]="planned"
            assert client.post(endpoint,json=own,headers={"Origin":ORIGIN}).status_code==200
            assert client.post(endpoint,json=own,headers={"Origin":ORIGIN}).status_code==200
            for change in ({"pack_on_hold":True},{"comparison":"yes"},{"batch_uploaded":"yes"},{"batch_revision":"a"*64}):
                assert client.post(endpoint,json={**own,**change,"submission_key":str(uuid4())},headers={"Origin":ORIGIN}).status_code==422
            assert client.post("/cases/6/end_user/findings",json=own,headers={"Origin":ORIGIN}).status_code==422
            with factory() as s:
                events=s.scalars(select(AlertDeskEvent).where(AlertDeskEvent.kind=="Findings submitted")).all()
                assert len(events)==3 and events[-1].data["own_cause"] is True
                assert s.get(CRMMah,crm_id) is not None
    finally:
        engine.dispose()
