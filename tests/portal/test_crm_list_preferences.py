import json
from types import SimpleNamespace

from fastapi import Request

from app.domain.models import PortalUser
from app.portal.crm_list_preferences import apply_saved_crm_filters, COLUMNS
from app.portal.routes import DbSession
from app.portal.crm_routes import router


def test_filter_preferences_are_personal_and_explicit_queries_win(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory.begin() as session:
        session.add_all([
            PortalUser(id=1, email="one@example.test", handle="one", is_admin=0, is_nmvo=1),
            PortalUser(id=2, email="two@example.test", handle="two", is_admin=0, is_nmvo=1),
        ])

    def identity(request: Request, session: DbSession):
        identifier = request.headers.get("x-test-user")
        if identifier:
            request.state.portal_user = SimpleNamespace(id=int(identifier))
        return apply_saved_crm_filters(request, session)

    client.app.dependency_overrides[apply_saved_crm_filters] = identity

    url = "/crm/list-preferences/mahs"
    headers = {"origin": "http://testserver", "x-test-user": "1"}
    data = {
        "visible": json.dumps(["q", "agreement"]),
        "defaults": json.dumps({"q": "", "archived": "false", "agreement": "missing"}),
    }
    assert client.post(url, data=data, headers=headers).status_code == 200
    assert client.get(url, headers=headers).json()["visible"] == ["q", "agreement"]
    assert client.get(url, headers={"x-test-user": "2"}).json()["defaults"] is None
    redirect = client.get("/crm/mahs", headers=headers, follow_redirects=False)
    assert redirect.status_code == 200  # Named views now own default selection.
    assert client.get("/crm/mahs?agreement=linked", headers=headers).status_code == 200
    assert client.get("/crm/mahs?q=", headers=headers).status_code == 200
    assert client.post(url, data=data, headers={"x-test-user": "1"}).status_code == 403
    assert client.post(url, data=data).status_code == 401
    invalid = {**data, "defaults": json.dumps({"q": "", "archived": "false", "user_id": "2"})}
    assert client.post(url, data=invalid, headers=headers).status_code == 422
    order = ["contract", "name", "uid", "registration", "gln"]
    expected_order = order + [key for key in COLUMNS["mahs"] if key not in order]
    columns = {
        "command": "save-columns",
        "columns": json.dumps(["contract", "name", "gln"]),
        "column_order": json.dumps(order),
    }
    assert client.post(url, data=columns, headers=headers).status_code == 200
    saved = client.get(url, headers=headers).json()
    assert saved["columns"] == ["contract", "name", "gln"]
    assert saved["column_order"] == expected_order
    assert saved["defaults"]["agreement"] == "missing"
    assert client.get(url, headers={"x-test-user": "2"}).json()["columns"] is None
    assert client.post(url, data={**columns, "columns": '["uid"]'}, headers=headers).status_code == 422
    assert client.post(url, data={**columns, "columns": '["name", "unknown"]'}, headers=headers).status_code == 422
    assert client.post(url, data={**columns, "column_order": '["name"]'}, headers=headers).status_code == 422
    assert client.post(url, data={**columns, "column_order": '["name", "gln", "uid", "registration", "gln"]'}, headers=headers).status_code == 422
    assert client.post(url, data=data, headers=headers).status_code == 200
    assert client.get(url, headers=headers).json()["column_order"] == expected_order
    assert client.get(url, headers=headers).json()["columns"] == ["contract", "name", "gln"]
    assert client.post(url, data={"command": "reset"}, headers=headers).status_code == 200
    saved = client.get(url, headers=headers).json()
    assert saved["columns"] == ["contract", "name", "gln"] and saved["defaults"] == {}
    assert client.post(url, data=data, headers=headers).status_code == 200
    assert client.post(url, data={"command": "reset-columns"}, headers=headers).status_code == 200
    saved = client.get(url, headers=headers).json()
    assert saved["columns"] is None and saved["column_order"] is None and saved["defaults"]["agreement"] == "missing"
    assert client.post(url, data={"command": "reset"}, headers=headers).status_code == 200
    assert client.get(url, headers=headers).json()["defaults"] is None
    assert client.get("/crm/mahs", headers=headers).status_code == 200
