import json
import re
from types import SimpleNamespace

import pytest
from fastapi import Request
from sqlalchemy import select

from app.domain.models import CRMListView, CRMMah, CRMSelfDeclaration, PortalUser
from app.integration.artifacts.storage import utcnow
from app.portal.crm_list_preferences import apply_saved_crm_filters
from app.portal.crm_routes import router
from app.portal.routes import DbSession


@pytest.fixture
def views_portal(portal):
    client, factory = portal
    client.app.include_router(router)
    with factory.begin() as session:
        session.add_all(
            [
                PortalUser(
                    id=1, email="one@example.test", handle="one", is_admin=0, is_nmvo=1
                ),
                PortalUser(
                    id=2, email="two@example.test", handle="two", is_admin=0, is_nmvo=1
                ),
            ]
        )

    def identity(request: Request, session: DbSession):
        identifier = request.headers.get("x-test-user")
        if identifier:
            request.state.portal_user = SimpleNamespace(id=int(identifier))
        return apply_saved_crm_filters(request, session)

    client.app.dependency_overrides[apply_saved_crm_filters] = identity
    return client, factory


def post_view(client, directory="mahs", *, user=1, **fields):
    return client.post(
        "/crm/views/" + directory,
        headers={
            "origin": "http://testserver",
            "x-test-user": str(user),
        },
        data={
            key: json.dumps(value) if key == "config" else value
            for key, value in fields.items()
        },
    )


def test_views_are_personal_versioned_and_have_one_default(views_portal):
    client, factory = views_portal
    config = {
        "conditions": [
            {"field": "agreement_count", "operator": "equals", "value": "0"}
        ],
        "columns": ["name", "gln"],
        "column_order": ["gln", "name", "uid", "registration", "contract"],
    }
    response = post_view(
        client, command="create", name="No agreement", config=config, is_default="true"
    )
    assert response.status_code == 200
    row = response.json()["view"]
    assert row["config"]["column_order"][:2] == ["gln", "name"]
    assert (
        client.get(
            "/crm/mahs", headers={"x-test-user": "1"}, follow_redirects=False
        ).headers["location"]
        == f"/crm/mahs?view={row['id']}"
    )
    assert (
        client.get("/crm/views/mahs", headers={"x-test-user": "2"}).json()["views"]
        == []
    )
    assert (
        client.get(
            f"/crm/mahs?view={row['id']}", headers={"x-test-user": "2"}
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/crm/contacts?view={row['id']}", headers={"x-test-user": "1"}
        ).status_code
        == 404
    )
    assert (
        post_view(
            client,
            command="save",
            id=row["id"],
            version=row["version"],
            name="Other",
            config=config,
            user=2,
        ).status_code
        == 404
    )
    assert (
        post_view(
            client, command="save", id=row["id"], version=0, name="Other", config=config
        ).status_code
        == 409
    )
    assert (
        post_view(
            client, command="create", name="NO AGREEMENT", config=config
        ).status_code
        == 409
    )
    second = post_view(
        client, command="create", name="Second", config={}, is_default="true"
    ).json()["view"]
    with factory() as session:
        default_ids = list(
            session.scalars(select(CRMListView.id).where(CRMListView.is_default == 1))
        )
        assert default_ids == [second["id"]]
    assert (
        post_view(
            client, command="delete", id=second["id"], version=second["version"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/crm/mahs", headers={"x-test-user": "1"}, follow_redirects=False
        ).status_code
        == 200
    )
    assert (
        client.get("/crm/mahs?view=all", headers={"x-test-user": "1"}).status_code
        == 200
    )
    assert (
        client.get(
            "/crm/mahs?view=99999999999999999999999999", headers={"x-test-user": "1"}
        ).status_code
        == 404
    )


def test_typed_conditions_sort_before_paging_and_scope_detail_navigation(views_portal):
    client, factory = views_portal
    with factory.begin() as session:
        now = utcnow()
        mah = CRMMah(
            name="Example", contract_status="unknown", created_at=now, updated_at=now
        )
        session.add(mah)
        session.flush()
        declarations = []
        for packs in range(85):
            item = CRMSelfDeclaration(
                source_key=str(packs),
                record_label=f"Declaration {packs:03}",
                source_mah_name="Example",
                declaration_year=2026,
                packs_sold=packs,
                mah_id=mah.id,
            )
            session.add(item)
            declarations.append(item)
        session.flush()
        id_by_packs = {item.packs_sold: item.id for item in declarations}
    config = {
        "quick_filters": {"year": "2026"},
        "conditions": [{"field": "packs", "operator": "greater_than", "value": "20"}],
        "sort": "packs",
        "direction": "desc",
    }
    view = post_view(
        client, "self-declarations", command="create", name="High volume", config=config
    ).json()["view"]
    headers = {"x-test-user": "1"}
    url = f"/crm/self-declarations?view={view['id']}"
    first = client.get(url, headers=headers)
    assert first.status_code == 200
    assert "64" in first.text and "Page 1 / 2" in first.text
    rows = re.findall(r"/crm/self-declarations/(\d+)\?", first.text)
    assert list(map(int, rows)) == [id_by_packs[packs] for packs in range(84, 44, -1)]
    second = client.get(url + "&page=2", headers=headers)
    rows = re.findall(r"/crm/self-declarations/(\d+)\?", second.text)
    assert list(map(int, rows)) == [id_by_packs[packs] for packs in range(44, 20, -1)]
    detail = client.get(
        f"/crm/self-declarations/{id_by_packs[45]}?view={view['id']}", headers=headers
    ).text
    assert f'rel="next" href="/crm/self-declarations/{id_by_packs[44]}?' in detail
    assert f"view={view['id']}" in detail
    # An unsaved preview uses the same engine, including a numeric zero value.
    rules = json.dumps([{"field": "packs", "operator": "equals", "value": "0"}])
    empty_scope = client.get(
        "/crm/self-declarations",
        params={"view": "all", "rules": rules},
        headers=headers,
    ).text
    assert "Declaration 000" in empty_scope and "Declaration 001" not in empty_scope


@pytest.mark.parametrize(
    "config",
    [
        {"conditions": [{"field": ["name"], "operator": "equals", "value": "Example"}]},
        {"conditions": [{"field": "name", "operator": "greater_than", "value": "1"}]},
        {
            "conditions": [
                {"field": "eligible_for_invoicing", "operator": "equals", "value": 1}
            ]
        },
        {
            "conditions": [
                {"field": "agreement_count", "operator": "equals", "value": "NaN"}
            ]
        },
        {
            "conditions": [
                {"field": "created_at", "operator": "before", "value": "yesterday"}
            ]
        },
        {"sort": ["name"]},
        {"columns": ["source_auth_code", "name"]},
    ],
)
def test_view_conditions_reject_invalid_types_and_fields(views_portal, config):
    client, _ = views_portal
    assert post_view(client, command="preview", config=config).status_code == 422


def test_boolean_and_relationship_conditions_use_current_crm_evidence(views_portal):
    from app.domain.models import CRMAgreement

    client, factory = views_portal
    with factory.begin() as session:
        now = utcnow()
        for name, status, eligible in [
            ("Ready", "Signed", True),
            ("Unpaid", "Signed", False),
            ("Old", "Terminated", True),
            ("Missing", None, True),
        ]:
            mah = CRMMah(
                name=name,
                contract_status="unknown",
                created_at=now,
                updated_at=now,
                profile={"eligible_for_invoicing": eligible},
            )
            session.add(mah)
            if status:
                session.add(
                    CRMAgreement(
                        contract_id=name, contractor=name, status=status, mahs=[mah]
                    )
                )
    config = {
        "conditions": [
            {"field": "contract", "operator": "contains", "value": "Signed"},
            {"field": "eligible_for_invoicing", "operator": "equals", "value": True},
        ]
    }
    view = post_view(client, command="create", name="Ready", config=config).json()[
        "view"
    ]
    page = client.get(f"/crm/mahs?view={view['id']}", headers={"x-test-user": "1"}).text
    assert ">Ready</span>" in page
    assert (
        ">Old</span>" not in page
        and ">Unpaid</span>" not in page
        and ">Missing</span>" not in page
    )
    presets = client.get("/crm/views/mahs", headers={"x-test-user": "1"}).json()[
        "presets"
    ]
    assert {item["id"] for item in presets} == {
        "no-agreement",
        "no-signed-agreement",
        "declaration-ready",
    }
