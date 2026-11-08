"""Start a disposable local CRM and declaration-workflow workspace."""

import hashlib
import os
import re
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.db.models import Base
from app.core.db.safety import ALLOWED_DATABASE_NAME
from app.core.db.session import GuardedSession, get_session
from app.domain.crm.declaration_fees import SALES_FEES, calculate_fees
from app.domain.models import CRMAgreement, CRMContact, CRMDeclarationDraft, CRMMah
from app.integration.artifacts.storage import utcnow
from app.portal.auth_access import install_portal_access
from app.portal.crm_routes import router as crm_router
from app.portal.exception_routes import review_form
from app.portal.routes import DbSession, templates
from app.portal.routes import router as portal_router
from app.portal.workflow_routes import router as workflow_router

PORT = 8013


def seed(factory):
    with factory.begin() as session:
        contacts = [
            CRMContact(
                airtable_id=f"fixture-{index}",
                label=f"Fixture SPOC {index}",
                profile={"email": f"spoc{index}@example.test"},
            )
            for index in (1, 2)
        ]
        session.add_all(contacts)
        session.flush()
        for name, direct, status, spocs in (
            (
                "Fixture MAH · Two SPOCs",
                True,
                "Signed",
                [contact.id for contact in contacts],
            ),
            ("Fixture MAH · Missing SPOC", True, "Signed", []),
            ("Fixture MAH · Indirect billing", False, "Signed", [contacts[0].id]),
            (
                "Fixture MAH · Terminated agreement",
                True,
                "Terminated",
                [contacts[0].id],
            ),
        ):
            now = utcnow()
            mah = CRMMah(
                name=name,
                contract_status="unknown",
                created_at=now,
                updated_at=now,
                profile={"eligible_for_invoicing": direct, "spoc_ids": spocs},
            )
            session.add(
                CRMAgreement(
                    contract_id=f"FIXTURE-{status}-{len(spocs)}-{int(direct)}",
                    contractor=name,
                    status=status,
                    mahs=[mah],
                )
            )


def install_form_simulator(app):
    receipts = {}
    by_draft = {}
    lock = Lock()

    def invitation(session, auth_code):
        digest = hashlib.sha256(auth_code.encode()).hexdigest()
        draft = session.scalar(
            select(CRMDeclarationDraft).where(
                CRMDeclarationDraft.token_digest == digest
            )
        )
        if draft is None:
            raise HTTPException(404, "Test invitation not found.")
        return draft

    @app.get("/test-form")
    def form(
        request: Request, session: DbSession, auth_code: str = Query(..., max_length=64)
    ):
        draft = invitation(session, auth_code)
        with lock:
            existing = by_draft.get(draft.id)
        if existing:
            return RedirectResponse(f"/test-form/receipts/{existing}", status_code=303)
        mah = session.get(CRMMah, draft.mah_id)
        return templates.TemplateResponse(
            request=request,
            name="test_declaration_form.html",
            context={
                "title": "Test self-declaration",
                "mah": mah,
                "draft": draft,
                "auth_code": auth_code,
                "sales_groups": SALES_FEES,
            },
            headers={"Cache-Control": "no-store", "Referrer-Policy": "same-origin"},
        )

    @app.post("/test-form")
    async def submit(request: Request, session: DbSession):
        data = await review_form(request)
        draft = invitation(session, data.get("auth_code", ""))
        if not draft.approved_at:
            raise HTTPException(
                409, "Approve the draft before simulating a submission."
            )
        packs = data.get("packs", "").strip()
        sales_group = data.get("sales_group", "")
        po_number = data.get("po_number", "").strip()
        if not re.fullmatch(r"[0-9]{1,12}", packs) or len(po_number) > 100:
            raise HTTPException(
                422, "Enter a valid pack count and purchase order number."
            )
        try:
            fees = calculate_fees(int(packs), sales_group, draft.base_fee)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        mah = session.get(CRMMah, draft.mah_id)
        with lock:
            key = by_draft.get(draft.id)
            if key is None:
                key = secrets.token_urlsafe(32)
                by_draft[draft.id] = key
                receipts[key] = {
                    "mah_name": mah.name,
                    "data_year": draft.data_year,
                    "packs": int(packs),
                    "sales_group": sales_group,
                    "po_number": po_number,
                    "fees": fees,
                }
        return RedirectResponse(f"/test-form/receipts/{key}", status_code=303)

    @app.get("/test-form/receipts/{key}")
    def receipt(request: Request, key: str):
        with lock:
            result = receipts.get(key)
        if result is None:
            raise HTTPException(404, "Test receipt not found.")
        return templates.TemplateResponse(
            request=request,
            name="test_declaration_receipt.html",
            context={"title": "Test submission received", **result},
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )


def main():
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["LOGO_DEV_PUBLISHABLE_KEY"] = ""
    os.environ["DECLARATION_INVITATION_SECRET"] = "isolated-fixture-invitation-secret"
    with TemporaryDirectory(prefix="smvs-fixture-") as directory:
        engine = create_engine("sqlite:///" + str(Path(directory) / "fixture.db"))

        @event.listens_for(engine, "connect")
        def configure(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.create_function("DATABASE", 0, lambda: ALLOWED_DATABASE_NAME)

        Base.metadata.create_all(engine)
        factory = sessionmaker(
            engine,
            class_=GuardedSession,
            configured_database=ALLOWED_DATABASE_NAME,
            expire_on_commit=False,
        )
        seed(factory)
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        settings = get_settings().model_copy(
            update={"portal_auth_enabled": False, "environment": "development"}
        )
        install_portal_access(app, settings)
        app.state.test_workspace = True
        app.state.declaration_form_url = f"http://localhost:{PORT}/test-form"
        app.mount(
            "/portal-static",
            StaticFiles(directory=Path(__file__).parent / "static"),
            name="portal_static",
        )

        def fixture_session():
            with factory() as session:
                yield session

        app.dependency_overrides[get_session] = fixture_session
        app.include_router(portal_router)
        app.include_router(crm_router)
        app.include_router(workflow_router)

        install_form_simulator(app)

        try:
            uvicorn.run(app, host="127.0.0.1", port=PORT, access_log=False)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
