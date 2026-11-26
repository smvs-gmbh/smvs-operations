import re
from html import unescape
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.alert_desk.test_workspace import ORIGIN, create_workspace, fixture_database


def test_three_roles_and_batch_reset(tmp_path):
    engine, factory = fixture_database(tmp_path / "alert-desk.db")
    try:
        with TestClient(
            create_workspace(factory), base_url=ORIGIN, client=("127.0.0.1", 1234)
        ) as client:
            headers = {"Origin": ORIGIN}
            overview = client.get("/")
            assert "DEMO-A24-1" in overview.text
            assert "portal-list-views.js" not in overview.text
            assert "<span>Case status</span><span>Date (UTC)</span>" in overview.text
            assert "Test pharmacy" in overview.text and "Test MAH" in overview.text
            assert "DEMO-A2</" not in overview.text
            assert overview.headers["Referrer-Policy"] == "same-origin"
            audit = client.get("/exceptions/4/audit-trail")
            assert audit.status_code == 200
            assert "Synthetic demo report" in audit.text
            assert "Active → Exported" in audit.text and "This exception" in audit.text
            download = re.search(
                r'href="(/pack-audit/reports/\d+/original)"', audit.text
            )[1]
            assert b"Synthetic demo report" in client.get(download).content
            assert (
                client.post("/exceptions/4/audit-trail", headers=headers).status_code
                == 405
            )
            assert "Your investigation" not in client.get("/cases/6/end_user").text
            end_user = client.get("/cases/1/end_user").text
            mah = client.get("/cases/1/mah").text
            assert "Was this batch uploaded?" in mah
            assert "Update findings for this batch (2 alerts)" in end_user
            assert client.get("/cases/4/end_user").status_code == 404
            basis = re.search(r'name="basis" value="([^"]+)"', end_user)[1]
            batch = re.search(r'data-batch-revision="([^"]+)"', end_user)[1]
            findings = {
                "publication": 1,
                "basis": basis,
                "batch_revision": batch,
                "finding": "not_my_side",
                "submission_key": str(uuid4()),
                "comparison": "yes",
            }
            assert client.post(
                "/cases/1/end_user/findings", json=findings, headers=headers
            ).json() == {"received": True, "batch_count": 2}
            assert client.post(
                "/cases/1/mah/findings",
                headers=headers,
                json={
                    "publication": 1,
                    "basis": basis,
                    "finding": "other",
                    "batch_uploaded": "no",
                    "capa": "planned",
                    "batch_revision": batch,
                    "submission_key": str(uuid4()),
                },
            ).json() == {"received": True, "batch_count": 2}
            filtered = client.get(
                "/", params={"mah_finding": "Batch was not uploaded"}
            ).text
            assert "DEMO-A2-1" in filtered and "DEMO-A2-2" in filtered
            assert "DEMO-A3-1" not in filtered
            case_id = re.search(r"<strong>(TEST-[A-F0-9]+)</strong>", filtered)[1]
            assert filtered.count('class="test-case-group"') == 1
            assert "Batch was not uploaded" not in filtered
            url = "/exceptions/1/analysis"
            analysis = client.get(url).text
            assert f"/?case={case_id}#alert-1" in analysis
            assert 'href="/cases/1/end_user"' in analysis
            assert 'href="/cases/1/mah"' in analysis
            assert (
                "Root cause not on my side" in analysis and "CAPA · Planned" in analysis
            )
            assert "<strong>Root cause on my side</strong>" in analysis
            assert "Batch was not uploaded" in analysis
            assert "Other issue on my side" not in analysis
            state = re.search(r'name="state" value="([^"]+)"', analysis)[1]
            link = unescape(
                re.search(r'href="(/\?batch_source=[^"]+)">View 2 alerts', analysis)[1]
            )
            scoped = client.get(link).text
            assert "DEMO-A2-1" in scoped and "DEMO-A2-2" in scoped
            assert "DEMO-A3-1" not in scoped
            preview = client.post(
                url + "/batches",
                headers=headers,
                data={"state": state, "origin": "mah"},
            )
            assert preview.status_code == 200
            assert preview.headers["Referrer-Policy"] == "same-origin"
            assert preview.text.count("<strong>2/2</strong>") == 2
            assert "Batch was not uploaded" in preview.text
            assert "Closed by SMVS" not in client.get("/cases/2/mah").text
            state = re.search(r'name="state" value="([^"]+)"', preview.text)[1]
            decision = {"state": state, "origin": "mah", "command": "close_batches"}
            assert (
                client.post(
                    url + "/batches", headers=headers, data=decision
                ).status_code
                == 422
            )
            flag = client.post(
                "/cases/2/individual-review",
                headers=headers,
                data={"action": "flag", "reason": "Printed serial needs review."},
                follow_redirects=False,
            )
            assert (
                flag.headers["location"] == "/exceptions/2/analysis#individual-review"
            )
            assert (
                "Printed serial needs review."
                in client.get(flag.headers["location"]).text
            )
            assert "Individual review required" in client.get(f"/?case={case_id}").text
            assert (
                client.post(
                    url + "/batches",
                    headers=headers,
                    data={**decision, "batch_0": "yes"},
                ).status_code
                == 409
            )
            preview = client.post(
                url + "/batches",
                headers=headers,
                data={
                    "state": re.search(r'name="state" value="([^"]+)"', analysis)[1],
                    "origin": "mah",
                },
            )
            assert "1 eligible for batch closure" in preview.text
            assert "Printed serial needs review." in preview.text
            decision["state"] = re.search(
                r'name="state" value="([^"]+)"', preview.text
            )[1]
            assert (
                client.post(
                    url + "/batches",
                    headers=headers,
                    data={**decision, "batch_0": "yes"},
                    follow_redirects=False,
                ).status_code
                == 303
            )
            assert "Closed by SMVS" not in client.get("/cases/2/mah").text
            assert "Closed by SMVS" in client.get("/cases/1/mah").text
            assert (
                client.post("/cases/1/reset", data={"reset": "yes"}).status_code == 403
            )
            assert (
                client.post(
                    "/cases/1/reset",
                    data={"reset": "yes"},
                    headers=headers,
                    follow_redirects=False,
                ).status_code
                == 303
            )
            assert "Your investigation" in client.get("/cases/1/mah").text
            reset_overview = client.get("/").text
            assert case_id in reset_overview
            assert "Individual review required" not in reset_overview
            assert 'id="review-state" hidden' in client.get("/cases/2/end_user").text
            audit = client.get("/exceptions/1/work-audit").text
            assert "Closed by SMVS" not in audit
            assert "Root cause not on my side" not in client.get(url).text
            assert (
                client.post(
                    "/cases/1/end_user/findings", json=findings, headers=headers
                ).status_code
                == 409
            )
            assert (
                client.post(
                    "/reset", headers=headers, data={"reset": "yes"}
                ).status_code
                == 200
            )
            assert "DEMO-A24-1" in client.get("/").text
        with TestClient(
            create_workspace(factory), base_url=ORIGIN, client=("127.0.0.1", 1234)
        ) as restarted:
            assert "Your investigation" in restarted.get("/cases/1/mah").text
            assert download in restarted.get("/exceptions/4/audit-trail").text
    finally:
        engine.dispose()


@pytest.mark.parametrize("role,finding", [
    ("end_user", "procedural"), ("end_user", "technical"), ("end_user", "other"),
    ("end_user", "not_my_side"), ("end_user", "investigating"),
    ("mah", "other"), ("mah", "not_my_side"), ("mah", "investigating"),
])
def test_optional_comment_survives_all_findings_and_round_trip(tmp_path, role, finding):
    from sqlalchemy import select

    from app.domain.models import AlertDeskEvent, NMVSException

    engine, factory = fixture_database(tmp_path / "comments.db")
    try:
        with TestClient(create_workspace(factory), base_url=ORIGIN, client=("127.0.0.1", 1234)) as client:
            if role == "end_user":
                with factory.begin() as session:
                    own = session.get(NMVSException, 4)
                    own.source_market = "CH"
                    own.organisation_id = "1"
                    own.source_location_id = "fixture-location"
                    own.is_intermarket = 0
                    own.business_process = "National System Single Pack API"
            path = f"/cases/4/{role}"
            body = client.get(path).text
            textarea = re.search(r'<textarea id="comment"[^>]*>', body)[0]
            assert 'disabled' not in textarea and 'maxlength="1000"' in textarea
            assert '<div id="comment-field">' in body
            basis = re.search(r'name="basis" value="([^"]+)"', body)[1]
            payload = {
                "publication": int(re.search(r'name="publication" value="([0-9]+)"', body)[1]),
                "basis": basis, "finding": finding,
                "submission_key": str(uuid4()),
                "comment": 'Scanner geprüft.\n<script>alert("source text")</script>',
                **({"capa": "planned"} if finding in {"procedural", "technical", "other"} else {}),
            }
            headers = {"Origin": ORIGIN}
            assert client.post(path+"/findings", headers=headers, json=payload).status_code == 200
            rendered = client.get(path).text
            assert 'Scanner geprüft.\n&lt;script&gt;' in rendered
            assert '<div id="review-comment" >' in rendered
            assert '<script>alert("source text")</script>' not in rendered
            with factory() as session:
                event = session.scalars(select(AlertDeskEvent).where(AlertDeskEvent.kind == "Findings submitted").order_by(AlertDeskEvent.id.desc())).first()
                assert event.data["comment"] == payload["comment"]
                assert event.data["finding"] == finding
            too_long = {**payload, "submission_key": str(uuid4()), "comment": "x"*1001}
            assert client.post(path+"/findings", headers=headers, json=too_long).status_code == 422
            empty = {**payload, "submission_key": str(uuid4()), "comment": ""}
            assert client.post(path+"/findings", headers=headers, json=empty).status_code == 200
    finally:
        engine.dispose()
