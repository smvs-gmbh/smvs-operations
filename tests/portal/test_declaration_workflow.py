from sqlalchemy import select

from app.domain.crm.imports import parse_export, stage_export
from app.domain.crm.mahs import seed_staged_mahs
from app.domain.models import (
    CRMAgreement,
    CRMContact,
    CRMDeclarationDraft,
    CRMMah,
    CRMSelfDeclaration,
)
from app.portal.workflow_routes import router

ORIGIN = {"origin": "http://testserver"}
PATH = "/workflows/self-declarations"


def test_preview_create_and_approve_declaration_drafts(portal, monkeypatch):
    client, factory = portal
    client.app.include_router(router)
    monkeypatch.setattr(
        "app.portal.workflow_routes.invitation_secret", lambda: "test-secret"
    )
    data = (
        b"RECORD_ID,MAH Name,Eligible for invoicing\n"
        b"recEligible,Eligible Holder,checked\nrecIndirect,Indirect Holder,\n"
        b"recUnsigned,Unsigned Holder,checked\n"
    )
    with factory() as s:
        stage_export(s, parse_export("MAH", data), data, "mahs.csv")
        seed_staged_mahs(s)
        eligible, indirect, unsigned = s.scalars(
            select(CRMMah).order_by(CRMMah.name)
        ).all()
        first = CRMContact(airtable_id="recFirst", label="first@example.test")
        second = CRMContact(airtable_id="recSecond", label="second@example.test")
        s.add_all([first, second])
        s.flush()
        eligible.profile = {"spoc_ids": [first.id, second.id]}
        s.add_all(
            [
                CRMAgreement(
                    contract_id="A",
                    contractor=eligible.name,
                    status="Signed",
                    mahs=[eligible, indirect],
                ),
                CRMAgreement(
                    contract_id="B",
                    contractor=eligible.name,
                    status="Signed",
                    mahs=[eligible],
                ),
                CRMAgreement(
                    contract_id="C",
                    contractor=unsigned.name,
                    status="Terminated",
                    mahs=[unsigned],
                ),
            ]
        )
        s.commit()
    preview = client.get(f"{PATH}?year=2025")
    assert (
        "Eligible Holder" in preview.text
        and "first@example.test, second@example.test" in preview.text
    )
    assert (
        "Indirect Holder" not in preview.text and "Unsigned Holder" not in preview.text
    )
    with factory() as s:
        s.add_all(
            [
                CRMSelfDeclaration(
                    source_key="sent",
                    record_label="Prior invitation",
                    source_mah_name=indirect.name,
                    mah_id=indirect.id,
                    declaration_year=2024,
                    status="Selfdeclaration sent",
                ),
                CRMSelfDeclaration(
                    source_key="progressed",
                    record_label="Prior invoice",
                    source_mah_name=indirect.name,
                    mah_id=indirect.id,
                    declaration_year=2024,
                    status="Invoice sent",
                ),
            ]
        )
        s.commit()
    comparison = client.get(f"{PATH}?year=2025").text
    assert "Previous cycle · invoice year 2025" in comparison
    assert "Selfdeclaration sent · 1" in comparison and "Invoice sent · 1" in comparison
    assert (
        "Eligible now without a linked declaration in the previous cycle (1)"
        in comparison
    )
    assert "Declared previously and outside the current eligible list (1)" in comparison
    for _ in range(2):
        assert (
            client.post(PATH, data={"year": "2025"}, headers=ORIGIN).status_code == 200
        )
    with factory() as s:
        draft = s.scalars(select(CRMDeclarationDraft)).one()
        identifier = draft.id
        assert draft.base_fee == 1500 and draft.approved_at is None
    url = f"{PATH}/{identifier}"
    page = client.get(url)
    assert page.status_code == 200
    assert page.headers["referrer-policy"] == "same-origin"
    assert 'rel="noopener noreferrer"' in page.text
    assert "auth_code=" in page.text
    assert "first@example.test\nsecond@example.test" in page.text
    assert "auth_code=" not in client.get(f"{PATH}?year=2025").text
    assert (
        client.post(
            url, data={"command": "approve", "base_fee": "1500"}, headers=ORIGIN
        ).status_code
        == 422
    )
    result = client.post(
        url,
        data={
            "command": "approve",
            "base_fee": "1550.00",
            "recipient_emails": "review@example.test, second@example.test\nREVIEW@example.test",
        },
        headers=ORIGIN,
    )
    assert result.status_code == 200 and ">Approved</span>" in result.text
    assert "No product/batch dataset" not in result.text
    assert "Base fee" not in result.text
    with factory() as s:
        draft = s.get(CRMDeclarationDraft, identifier)
        assert draft.approved_at is not None and draft.base_fee == 1500
        assert draft.recipient_emails == ["review@example.test", "second@example.test"]
    assert (
        client.post(url, data={"command": "reopen"}, headers=ORIGIN).status_code == 200
    )
