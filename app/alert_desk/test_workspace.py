"""Disposable Alert Desk and Operations workflow on http://localhost:8021."""

import secrets
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    event,
    select,
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from app.alert_desk.schema import FINDINGS, Findings
from app.alert_desk.test_pack_audits import seed_pack_audits
from app.alert_desk.web import ASSETS, DESIGN_ASSETS, render_case
from app.connect.protocol import PRIVATE_HEADERS, bounded_json, json_object
from app.core.db.models import (
    AcquiredArtifact,
    ArtifactContent,
    Base,
    IntegrationJob,
    ProcessingRun,
)
from app.core.db.safety import ALLOWED_DATABASE_NAME
from app.core.db.session import GuardedSession, get_session
from app.domain.investigations import access, access_api, pilot, rca
from app.domain.investigations.preview import ERRORS
from app.domain.mapping import key
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskCaseUpdate,
    AlertDeskEvent,
    AlertDeskExportAttribution,
    AlertDeskGrant,
    AlertDeskResponseRequest,
    CRMContact,
    CRMEndUser,
    CRMMah,
    CurrentPublication,
    ExceptionPublication,
    ExceptionReview,
    ExceptionReviewEvent,
    LocalLocation,
    LocalOrganisation,
    MappingRun,
    NMVSException,
    ParticipantMappingRun,
    ParticipantPublication,
    PortalUser,
    SAIHolder,
    SAIPackage,
    SAIPreparation,
)
from app.portal.exception_queries import enriched
from app.portal.exception_routes import review_form, router
from app.portal.pack_audit_routes import audit, original
from app.portal.routes import DbSession, templates

ORIGIN = "http://localhost:8021"
NS = "alert-desk-fixture"
GTIN = "07680000000000"
GLN = "7601000000000"
CODES = ("A2", "A3", "A7", "A24")
ROLE = Literal["end_user", "mah"]
TEST_METADATA = MetaData()
Table(
    NMVSException.__tablename__, TEST_METADATA, Column("id", Integer, primary_key=True)
)
REVIEW_FLAGS = Table(
    "alert_desk_test_review_flags",
    TEST_METADATA,
    Column(
        "exception_id",
        Integer,
        ForeignKey(f"{NMVSException.__tablename__}.id"),
        primary_key=True,
    ),
    Column("reason", String(250), nullable=False),
)


def fixture_database(path):
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.create_function("DATABASE", 0, lambda: ALLOWED_DATABASE_NAME)

    Base.metadata.create_all(engine)
    REVIEW_FLAGS.create(engine, checkfirst=True)
    return engine, sessionmaker(
        engine,
        class_=GuardedSession,
        configured_database=ALLOWED_DATABASE_NAME,
        expire_on_commit=False,
    )


def seed(factory, tokens):
    now = pilot.now()
    with factory.begin() as s:

        def add(model, **fields):
            row = model(**fields)
            s.add(row)
            s.flush()
            return row.id

        source = {
            "source_name": NS,
            "channel_name": "fixture",
            "report_type": "Fixture",
        }
        job_id = add(IntegrationJob, **source, status="succeeded", created_at=now)
        content_id = add(
            ArtifactContent,
            sha256=key(NS),
            content_length=len(NS),
            artifact_bytes=NS.encode(),
            created_at=now,
        )
        artifact_id = add(
            AcquiredArtifact,
            **source,
            integration_job_id=job_id,
            content_id=content_id,
            report_metadata={},
            received_at=now,
            processing_status="staged",
            created_at=now,
        )
        run = add(
            ProcessingRun,
            artifact_id=artifact_id,
            run_type="fixture",
            parser_version="fixture",
            transform_version="fixture",
            status="succeeded",
            started_at=now,
        )
        mapping = add(
            MappingRun,
            input_key=key(NS, "mapping"),
            snapshot_run_id=run,
            sai_run_id=run,
            source_namespace=NS,
            mapping_version="fixture",
            status="succeeded",
            started_at=now,
        )
        participants = add(
            ParticipantMappingRun,
            input_key=key(NS, "participants"),
            snapshot_run_id=run,
            source_namespace=NS,
            mapping_version="fixture",
            status="succeeded",
            started_at=now,
        )
        s.add_all(
            [
                CurrentPublication(
                    name="product-batch",
                    mapping_run_id=mapping,
                    source_namespace=NS,
                    snapshot_date=now.date(),
                    sai_exported_at=now,
                    published_at=now,
                ),
                ParticipantPublication(
                    name="participants",
                    mapping_run_id=participants,
                    source_namespace=NS,
                    snapshot_date=now.date(),
                    published_at=now,
                ),
            ]
        )
        holder = add(
            SAIHolder,
            holder_key=key(NS, "holder"),
            partner_number="fixture",
            company_name="Test MAH",
            gln=GLN,
            is_observed=1,
            last_mapping_run_id=mapping,
            evidence={},
        )
        preparation = add(
            SAIPreparation,
            preparation_key=key(NS, "preparation"),
            approval_number="fixture",
            preparation_name="Test medicinal product",
            holder_id=holder,
            is_observed=1,
            last_mapping_run_id=mapping,
            evidence={},
        )
        add(
            SAIPackage,
            package_key=key(NS, "pack"),
            preparation_id=preparation,
            sequence_number="1",
            package_code="1",
            gtin14=GTIN,
            is_observed=1,
            last_mapping_run_id=mapping,
            evidence={},
        )
        org = add(
            LocalOrganisation,
            source_key=key(NS, "org"),
            source_namespace=NS,
            source_organisation_id="1",
            organisation_name="Test pharmacy",
            is_observed=1,
            last_participant_run_id=participants,
            evidence={},
        )
        add(
            LocalLocation,
            source_key=key(NS, "location"),
            source_namespace=NS,
            source_location_id="fixture-location",
            source_organisation_id="1",
            organisation_id=org,
            organisation_link_status="matched",
            location_name="Test location",
            is_observed=1,
            last_participant_run_id=participants,
            evidence={},
        )
        actor = add(
            PortalUser,
            email="nmvo@example.test",
            handle="fixture",
            is_admin=1,
            is_nmvo=1,
        )
        for role, token in tokens.items():
            contact = add(
                CRMContact,
                airtable_id=f"fixture-{role}",
                label=f"Test {role} contact",
                profile={"email": f"{role}@example.test"},
            )
            profile = {"alert_contact_ids": [contact]}
            if role == "mah":
                crm = add(
                    CRMMah,
                    name="Test MAH",
                    gln=GLN,
                    profile=profile,
                    contract_status="unknown",
                    created_at=now,
                    updated_at=now,
                )
            else:
                crm = add(
                    CRMEndUser,
                    name="Test pharmacy",
                    organisation_id=org,
                    profile=profile,
                )
            add(
                AlertDeskAccess,
                role=role,
                crm_organisation_id=crm,
                contact_id=contact,
                contact_version=1,
                scope_key=GLN if role == "mah" else str(org),
                invited_by=actor,
                invited_at=now,
                sent_at=now,
                accepted_at=now,
                invite_expires_at=now,
                session_hash=pilot.digest(token),
                session_expires_at=now + timedelta(days=1),
                attempts_left=0,
            )
        publication = add(
            ExceptionPublication,
            input_key=key(NS, "alerts"),
            processing_run_id=run,
            source_namespace=NS,
            mapping_version="fixture",
            period_start=now,
            period_end=now,
            query_started_at=now,
            captured_at=now,
            published_at=now,
            statistics={},
        )
        for code in CODES:
            for index in range(1, 3 if code in {"A2", "A7"} else 2):
                foreign = code == "A7"
                case_id = add(
                    NMVSException,
                    alert_key=key(NS, code, index),
                    source_namespace=NS,
                    unique_alert_id=f"DEMO-{code}-{index}",
                    alert_at=now,
                    timestamp_status="valid",
                    error_code=code,
                    product_code_scheme="GTIN",
                    product_code=GTIN,
                    gtin14=GTIN,
                    serial_number=f"DEMO{code}{index}",
                    provided_batch=f"DEMO-{code}",
                    source_market="DE" if foreign else "CH",
                    organisation_id=None if foreign else "1",
                    source_location_id="fixture-export"
                    if foreign
                    else "fixture-location",
                    last_update_location_id="fixture-other-location"
                    if code == "A24"
                    else None,
                    business_process="National System Intermarket"
                    if foreign
                    else "National System Single Pack API",
                    is_intermarket=int(foreign or code == "A2"),
                    payload_hash=key(NS, code, index, "payload"),
                    selection_time=now,
                    first_observed_at=now,
                    last_observed_at=now,
                    last_publication_id=publication,
                    evidence={
                        "attemptedOperation": "EXPORTED"
                        if foreign
                        else "SUPPLIED"
                        if code == "A24"
                        else "VERIFIED"
                    },
                )
                if foreign and index == 1:
                    end_user = s.scalar(select(CRMEndUser.id))
                    add(
                        AlertDeskExportAttribution,
                        anchor_exception_id=case_id,
                        end_user_id=end_user,
                        source_namespace=NS,
                        source_market="DE",
                        source_location_id="fixture-export",
                        gtin14=GTIN,
                        batch="DEMO-A7",
                        from_at=now - timedelta(hours=1),
                        until_at=now + timedelta(hours=1),
                        reason="Synthetic export cohort",
                        confirmed_at=now,
                    )
    return actor


def submitted_batch_ids(session, record, role, finding):
    source_id = finding.data.get("batch_source") or record.id
    targets = session.scalars(
        select(AlertDeskGrant.exception_id)
        .join(AlertDeskEvent, AlertDeskEvent.grant_id == AlertDeskGrant.id)
        .where(
            AlertDeskEvent.submission_key == finding.submission_key,
            AlertDeskEvent.kind == "Findings submitted",
            AlertDeskGrant.publication["audience"].as_string() == role,
            (AlertDeskGrant.exception_id == source_id)
            | (AlertDeskEvent.data["batch_source"].as_integer() == source_id),
        )
    )
    return sorted(set(targets))


def batch_finding_links_for(session, record, findings):
    links = {}
    for role, finding in findings.items():
        if finding.data.get("batch_count") or finding.data.get("batch_source"):
            ids = submitted_batch_ids(session, record, role, finding)
            if len(ids) > 1:
                source = finding.data.get("batch_source") or record.id
                links[role] = (
                    f"/?batch_source={source}&role={role}&submission={finding.submission_key}",
                    len(ids),
                )
    return links


def case_id_for_alert(record):
    batch = record.provided_batch or record.stored_batch
    product = record.gtin14 or record.product_code
    identity = (
        (
            record.source_namespace,
            "GTIN" if record.gtin14 else record.product_code_scheme,
            product,
            batch,
        )
        if product and batch
        else (record.source_namespace, record.unique_alert_id)
    )
    return f"TEST-{key(*identity)[:12].upper()}"


def case_overview(session, alerts):
    groups = {}
    for view in enriched(session, alerts):
        alert = view["record"]
        organisation = view["organisation"]
        cohort = access.export_cohort(session, alert) if not organisation else None
        end_user = session.get(CRMEndUser, cohort.end_user_id) if cohort else None
        row = {
            "id": alert.id,
            "alert_id": alert.unique_alert_id,
            "date": alert.alert_at.date().isoformat() if alert.alert_at else None,
            "code": alert.error_code,
            "end_user": organisation.organisation_name
            if organisation
            else end_user.name
            if end_user
            else None,
            "mah": view["holder"],
            "closed": rca.resolved_for_source(view["review"], alert),
        }
        groups.setdefault(case_id_for_alert(alert), []).append(row)
    return groups


def individual_review_reasons(session, findings):
    manual_flags = {
        identifier: reason
        for identifier, reason in session.execute(select(REVIEW_FLAGS))
    }
    reasons = {identifier: [reason] for identifier, reason in manual_flags.items()}
    for identifier, roles in findings.items():
        end_user = roles.get("end_user")
        if end_user and end_user.data.get("comparison") == "no":
            reasons.setdefault(identifier, []).append(
                "Submitted and printed pack data differ."
            )
    return manual_flags, reasons


def reset_findings(session, ids):
    grants = select(AlertDeskGrant.id).where(AlertDeskGrant.exception_id.in_(ids))
    session.execute(delete(REVIEW_FLAGS).where(REVIEW_FLAGS.c.exception_id.in_(ids)))
    for model in (
        AlertDeskCaseUpdate,
        AlertDeskResponseRequest,
        ExceptionReviewEvent,
        ExceptionReview,
    ):
        session.execute(delete(model).where(model.exception_id.in_(ids)))
    session.execute(delete(AlertDeskEvent).where(AlertDeskEvent.grant_id.in_(grants)))
    session.execute(delete(AlertDeskGrant).where(AlertDeskGrant.exception_id.in_(ids)))
    for fixture in session.scalars(
        select(NMVSException).where(NMVSException.id.in_(ids))
    ):
        fixture.payload_hash = secrets.token_hex(32)
    session.commit()


def create_workspace(factory, *, origin=ORIGIN):
    tokens = {role: secrets.token_urlsafe(32) for role in ("end_user", "mah")}
    with factory.begin() as session:
        actor = session.scalar(
            select(PortalUser.id).where(PortalUser.handle == "fixture")
        )
        if actor is not None:
            for grant in session.scalars(select(AlertDeskAccess)):
                grant.session_hash = pilot.digest(tokens[grant.role])
                grant.session_expires_at = pilot.now() + timedelta(days=1)
    if actor is None:
        actor = seed(factory, tokens)
    seed_pack_audits(factory, NS, CODES)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.alert_desk_test_workspace = True
    app.state.alert_desk_test_url = "/"

    @app.middleware("http")
    async def local_only(request, call_next):
        if (
            request.headers.get("host") != origin.split("://", 1)[1]
            or not request.client
            or request.client.host not in {"127.0.0.1", "::1"}
        ):
            return PlainTextResponse("Use the local test workspace address.", 403)
        request.state.portal_auth_enabled = False
        request.state.portal_user = SimpleNamespace(
            id=actor,
            email="nmvo@example.test",
            is_nmvo=True,
            is_admin=True,
        )
        response = await call_next(request)
        response.headers.update(PRIVATE_HEADERS)
        # Native same-origin form POSTs must carry the workspace Origin.
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    def fixture_session():
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = fixture_session
    app.include_router(router)
    app.add_api_route("/exceptions/{identifier}/audit-trail", audit, methods=["GET"])
    app.add_api_route(
        "/pack-audit/reports/{report_id}/original", original, methods=["GET"]
    )
    app.mount(
        "/portal-static",
        StaticFiles(directory=ASSETS.parent / "portal/static"),
        name="portal_static",
    )
    app.mount("/case-assets/design", StaticFiles(directory=DESIGN_ASSETS))

    # Serve the participant assets without exposing application files.
    @app.get("/case-assets/{name}")
    def asset(name: Literal["case.css", "case.js", "comment-templates.js"]):
        return FileResponse(ASSETS / name)

    # Reuse the organisation endpoints against this isolated database, including
    # the same validation, batch selection and event persistence as Alert Desk.
    read_case, submit_case, template_api = access_api.install(
        FastAPI(), factory, secrets.token_urlsafe(32)
    )

    @app.get("/")
    def overview(
        request: Request,
        session: DbSession,
        mah_finding: str = "",
        batch_source: int | None = None,
        role: ROLE = "mah",
        submission: str = "",
        case: str = "",
    ):
        cases = session.scalars(select(NMVSException).order_by(NMVSException.id)).all()
        groups = case_overview(session, cases)
        visible_ids = {alert.id for alert in cases}
        if batch_source is not None:
            source = session.get(NMVSException, batch_source)
            anchor = (
                session.scalar(
                    select(AlertDeskEvent)
                    .join(AlertDeskGrant, AlertDeskEvent.grant_id == AlertDeskGrant.id)
                    .where(
                        AlertDeskGrant.exception_id == batch_source,
                        AlertDeskGrant.publication["audience"].as_string() == role,
                        AlertDeskEvent.submission_key == submission,
                        AlertDeskEvent.kind == "Findings submitted",
                    )
                )
                if source
                else None
            )
            if not anchor or not anchor.data.get("batch_count"):
                raise HTTPException(404, "Batch finding not found.")
            visible_ids = set(submitted_batch_ids(session, source, role, anchor))
        findings = rca.participant_findings(session, visible_ids)
        _, review_reasons = individual_review_reasons(session, findings)
        return templates.TemplateResponse(
            request=request,
            name="alert_desk_test_workspace.html",
            context={
                "title": "Alert Desk test workspace",
                "active": "test",
                "groups": groups,
                "visible_ids": visible_ids,
                "review_reasons": review_reasons,
                "expanded_case": case,
                "labels": ERRORS,
                "findings": findings,
                "finding_labels": FINDINGS,
                "mah_finding": mah_finding,
                "batch_source": batch_source,
            },
        )

    @app.get("/cases/{identifier}/{role}")
    def participant(request: Request, identifier: int, role: ROLE, session: DbSession):
        case = read_case(identifier, tokens[role])
        record = session.get(NMVSException, identifier)
        return render_case(
            request,
            case,
            message="Participant findings are unavailable for A24."
            if case["code"] == "A24"
            else "",
            assets="/case-assets",
            organisation_case=True,
            back_url=f"/?case={case_id_for_alert(record)}#alert-{identifier}"
            if record
            else "/",
            back_label="Test workspace",
            findings_url=f"/cases/{identifier}/{role}/findings",
        )

    @app.get("/cases/{identifier}/{role}/comment-templates")
    def comment_template_list(identifier: int, role: ROLE):
        return template_api[0](identifier, tokens[role])

    @app.get("/cases/{identifier}/{role}/comment-templates/{template_id}")
    def comment_template_detail(identifier: int, role: ROLE, template_id: int):
        return template_api[1](identifier, template_id, tokens[role])

    @app.post("/cases/{identifier}/{role}/comment-templates")
    async def comment_template_command(request: Request, identifier: int, role: ROLE):
        from app.domain.investigations.comment_templates import TemplateCommand

        if request.headers.get("origin") != origin:
            raise HTTPException(403, "Use the test workspace form.")
        try:
            body = TemplateCommand.model_validate(json_object(await bounded_json(request, 8192)))
        except (ValueError, TypeError):
            raise HTTPException(422, "Check the template name and text.") from None
        return await run_in_threadpool(template_api[2], identifier, body, tokens[role])

    @app.post("/cases/{identifier}/{role}/findings")
    async def findings(request: Request, identifier: int, role: ROLE):
        if request.headers.get("origin") != origin:
            raise HTTPException(403, "Use the test workspace form.")
        raw = await bounded_json(request, 4096)
        try:
            body = Findings.model_validate(json_object(raw))
        except (ValueError, TypeError):
            raise HTTPException(422, "Check your answers and try again.") from None
        return await run_in_threadpool(submit_case, identifier, body, tokens[role])

    @app.post("/cases/{identifier}/reset")
    async def reset(request: Request, identifier: int, session: DbSession):
        form = await review_form(request, expected_origin=origin)
        if form.get("reset") != "yes":
            raise HTTPException(422, "Confirm the test reset.")
        case = session.get(NMVSException, identifier)
        if not case:
            raise HTTPException(404, "Test case not found.")
        ids = [
            row.id
            for row in session.scalars(select(NMVSException))
            if case_id_for_alert(row) == case_id_for_alert(case)
        ]
        reset_findings(
            session, select(NMVSException.id).where(NMVSException.id.in_(ids))
        )
        return RedirectResponse("/", status_code=303)

    @app.post("/cases/{identifier}/individual-review")
    async def flag_review(request: Request, identifier: int, session: DbSession):
        form = await review_form(request, expected_origin=origin)
        case = session.get(NMVSException, identifier)
        if not case:
            raise HTTPException(404, "Test alert not found.")
        if form.get("action") == "clear":
            session.execute(
                delete(REVIEW_FLAGS).where(REVIEW_FLAGS.c.exception_id == identifier)
            )
        else:
            reason = form.get("reason", "").strip()
            if form.get("action") != "flag" or not 1 <= len(reason) <= 250:
                raise HTTPException(422, "Enter a reason of up to 250 characters.")
            statement = insert(REVIEW_FLAGS).values(
                exception_id=identifier, reason=reason
            )
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[REVIEW_FLAGS.c.exception_id],
                    set_={"reason": reason},
                )
            )
        session.commit()
        return RedirectResponse(
            f"/exceptions/{identifier}/analysis#individual-review", status_code=303
        )

    @app.post("/reset")
    async def reset_all(request: Request, session: DbSession):
        form = await review_form(request, expected_origin=origin)
        if form.get("reset") != "yes":
            raise HTTPException(422, "Confirm the test reset.")
        reset_findings(session, select(NMVSException.id))
        return RedirectResponse("/", status_code=303)

    return app


def main():
    directory = Path(__file__).resolve().parents[2] / "tmp" / "alert-desk-test"
    directory.mkdir(parents=True, exist_ok=True)
    engine, factory = fixture_database(directory / "fixtures.db")
    try:
        uvicorn.run(
            create_workspace(factory), host="127.0.0.1", port=8021, access_log=False
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
