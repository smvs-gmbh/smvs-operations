from fastapi.testclient import TestClient

from app.connect_preview.app import app


def test_synthetic_preview_is_isolated_and_exposes_only_its_assets():
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Fictional case" in page.text
        assert "Corrective measures will be taken" in page.text
        assert "Additional findings" in page.text
        assert "Corrective measures / comments" in page.text
        assert 'id="findings" rows="3" maxlength="2000"' in page.text
        assert page.headers["cache-control"] == "no-store"
        assert "connect-src 'none'" in page.headers["content-security-policy"]
        assert client.get("/preview.css").status_code == 200
        assert client.get("/preview.js").status_code == 200
        for path in ["/proposal", "/proposal.css", "/proposal.js", "/case-study", "/case-study.css", "/case-study.js", "/focused", "/focused.css", "/focused.js", "/compact", "/compact.css", "/compact.js", "/columns", "/columns.css", "/columns.js"]:
            proposal = client.get(path)
            assert proposal.status_code == 200
            assert "connect-src 'none'" in proposal.headers["content-security-policy"]
        assert client.post("/proposal", json={"finding": "technical"}).status_code == 405
        for path in ["/crm", "/exceptions", "/confirm", "/.env", "/docs", "/openapi.json"]:
            assert client.get(path).status_code == 404
        assert client.post("/", json={"finding": "procedural"}).status_code == 405
        assert client.post("/webhooks/tally/registrations", json={}).status_code == 404
