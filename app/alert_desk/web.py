"""Stateless local browser gateway for SMVS Alert Desk."""

import json
import os
import time
from collections import deque
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.alert_desk.schema import (
    CAPA,
    COMPARISON,
    COOKIE,
    FINDINGS,
    GRANT_HOURS,
    OWN_SIDE,
    PRIVATE_ORIGIN,
    PUBLIC_ORIGIN,
    SESSION_PATH,
    Capability,
    Findings,
    MailboxCode,
)
from app.connect.protocol import PRIVATE_HEADERS as CONNECT_PRIVATE_HEADERS
from app.connect.protocol import bounded_json, json_object

PRIVATE_HEADERS = {
    **CONNECT_PRIVATE_HEADERS,
    "Content-Security-Policy": CONNECT_PRIVATE_HEADERS["Content-Security-Policy"] + "; img-src 'self'",
}

ASSETS = Path(__file__).parent
BRAND_FILES = {"smvs-alert-desk-wide.png", "smvs-alert-desk-narrow.png"}
DESIGN_ASSETS = ASSETS.parent / "connect_preview" / "assets"
ACCESS_COOKIE = "alert_desk_access"
CHALLENGE_COOKIE = "alert_desk_mailbox_check"
DESIGN_STYLES = {"focused.css", "compact.css", "columns.css"}
templates = Jinja2Templates(directory=str(ASSETS))


def template_context(request, case, *, my_cases_url="/alerts"):
    # Build internal destinations; never accept a caller-supplied return URL.
    context = case.get("draft_context", "")
    if len(context) != 64 or any(c not in "0123456789abcdef" for c in context):
        raise HTTPException(503, "Verified draft context is unavailable. Reload the case.")
    path = request.url.path.removesuffix("/templates")
    query = urlencode({k: request.query_params[k][:100] for k in ("view", "finding", "q", "before") if k in request.query_params})
    suffix = "?" + query if query else ""
    return {
        "library_url": path + "/templates" + suffix,
        "case_url": path + suffix,
        "my_cases_url": my_cases_url + suffix if my_cases_url == "/alerts" else my_cases_url,
        "template_api": path + "/comment-templates",
        "draft_key": "alert-desk-template-draft:" + context + ":" + str(case["publication"]),
        "draft_revision": sha256(json.dumps({k: case.get(k) for k in ("basis", "latest", "progress", "batch_revision")}, sort_keys=True).encode()).hexdigest(),
    }


def render_template_library(request, case, *, assets="/alerts", my_cases_url="/alerts"):
    return templates.TemplateResponse(request=request, name="comment_templates.html", context={
        "case": case, "assets": assets, "library_active": True,
        "create_from_draft": request.query_params.get("create") == "1",
        "from_case_list": request.query_params.get("return") == "cases",
        **template_context(request, case, my_cases_url=my_cases_url),
    })


def render_case(
    request,
    case,
    *,
    message="",
    preview=False,
    assets="/alerts",
    organisation_case=False,
    status_code=200,
    back_url="/alerts",
    findings_url=None,
    back_label="My cases",
):
    return templates.TemplateResponse(
        request=request,
        name="case.html",
        status_code=status_code,
        context={
            "case": case,
            **(template_context(request, case, my_cases_url=back_url)
               if case and organisation_case and not preview else {}),
            "message": message,
            "key": uuid4(),
            "comparison": COMPARISON,
            "findings": FINDINGS,
            "own_side": OWN_SIDE,
            "capa": CAPA,
            "preview": preview,
            "assets": assets,
            "organisation_case": organisation_case,
            "back_url": back_url,
            "back_label": back_label,
            "findings_url": findings_url,
        },
    )


def create_app(secret, *, transport=None, public_origin=PUBLIC_ORIGIN, private_origin=PRIVATE_ORIGIN):
    from app.alert_desk.settings import AlertDeskSettings

    origins = AlertDeskSettings(
        alert_desk_public_origin=public_origin,
        alert_desk_private_origin=private_origin,
    )
    public_origin = origins.alert_desk_public_origin
    private_origin = origins.alert_desk_private_origin
    if len(secret) < 32:
        raise ValueError(
            "Set a dedicated Alert Desk pilot secret of at least 32 characters."
        )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.alert_desk_test = origins.environment == "test"
    recent_commands = deque()

    @app.middleware("http")
    async def protect(request, call_next):
        if (
            request.headers.get("host") != urlsplit(public_origin).netloc
            or not request.client
            or request.client.host not in {"127.0.0.1", "::1"}
        ):
            return HTMLResponse(
                "Use the configured Alert Desk address.", 403, headers=PRIVATE_HEADERS
            )
        # TLS terminates at the configured edge; construct links/redirects from
        # that fixed origin, never from a client-supplied forwarded scheme.
        request.scope["scheme"] = urlsplit(public_origin).scheme
        # Aggregate ceiling at the same-node proxy boundary. Do not treat an
        # arbitrary forwarded IP as a verified client identity.
        if request.method == "POST":
            now = time.monotonic()
            while recent_commands and recent_commands[0] <= now - 60:
                recent_commands.popleft()
            if len(recent_commands) >= 120:
                return JSONResponse(
                    {"detail": "Too many requests. Try again in a minute."}, 429,
                    headers={**PRIVATE_HEADERS, "Retry-After": "60"},
                )
            recent_commands.append(now)
        response = await call_next(request)
        response.headers.update(PRIVATE_HEADERS)
        return response

    async def forward(method, path, *, session=None, payload=None, params=None):
        headers = {"Authorization": "Bearer " + secret}
        if session:
            headers["X-Case-Session"] = session
        try:
            async with (
                httpx.AsyncClient(
                    trust_env=False, transport=transport, timeout=5
                ) as client,
                client.stream(
                    method,
                    private_origin + path,
                    headers=headers,
                    json=payload,
                    params=params,
                ) as response,
            ):
                if response.status_code == 404:
                    raise HTTPException(404, "This case or invitation is unavailable.")
                if response.status_code == 422:
                    raise HTTPException(422, "Check your answers and try again.")
                if response.status_code == 409:
                    raise HTTPException(409, "Reload the case before submitting.")
                if response.status_code == 200:
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > 32768:
                            raise ValueError("Response too large.")
                        body.extend(chunk)
                    return json_object(body)
        except (httpx.HTTPError, ValueError, TypeError):
            pass
        raise HTTPException(503, "Alert Desk is temporarily unavailable. Try again.")

    async def command(request, schema, *, limit=4096):
        if request.headers.get("origin") != public_origin:
            raise HTTPException(403, "Use the Alert Desk form.")
        raw = await bounded_json(request, limit)
        try:
            return schema.model_validate(json_object(raw))
        except (ValueError, TypeError):
            raise HTTPException(422, "Check your answers and try again.") from None

    @app.get("/alerts")
    async def page(
        request: Request,
        before: int | None = None,
        view: str = "my_cases",
        finding: str = "all",
        q: str = "",
    ):
        filters = {
            "view": view
            if view in {"my_cases", "completed", "on_hold", "all"}
            else "my_cases",
            "finding": finding
            if finding in {"all", "new", "investigating", "not_my_side", "on_my_side"}
            else "all",
            "q": q.strip()[:100],
        }
        access_session = request.cookies.get(ACCESS_COOKIE)
        if access_session:
            try:
                listing = await forward(
                    "GET",
                    "/access/alerts",
                    session=access_session,
                    params={**filters, **({"before": before} if before else {})},
                )
            except HTTPException as error:
                if error.status_code != 404:
                    return render_case(request, None, message=error.detail)
            else:
                return templates.TemplateResponse(
                    request=request,
                    name="access.html",
                    context={
                        "listing": listing,
                        "filters": filters,
                        "list_query": urlencode(
                            {**filters, **({"before": before} if before else {})}
                        ),
                    },
                )
        case = None
        message = ""
        session = request.cookies.get(COOKIE)
        if session:
            try:
                case = await forward("GET", "/case", session=session)
            except HTTPException as error:
                if error.status_code != 404:
                    message = error.detail
        return render_case(request, case, message=message)

    @app.get("/alerts/case.js")
    def script():
        return FileResponse(ASSETS / "case.js", media_type="text/javascript")

    @app.get("/alerts/comment-templates.js")
    def comment_template_script():
        return FileResponse(ASSETS / "comment-templates.js", media_type="text/javascript")

    @app.get("/alerts/portal.css")
    def portal_stylesheet():
        return FileResponse(
            ASSETS.parent / "portal" / "static" / "portal.css", media_type="text/css"
        )

    @app.get("/alerts/case.css")
    def stylesheet():
        return FileResponse(ASSETS / "case.css", media_type="text/css")

    @app.get("/alerts/brand/{name}")
    def brand_image(name: str):
        if name not in BRAND_FILES:
            raise HTTPException(404)
        return FileResponse(ASSETS / "brand" / name, media_type="image/png")

    @app.get("/alerts/design/{name}")
    def design_stylesheet(name: str):
        if name not in DESIGN_STYLES:
            raise HTTPException(404)
        return FileResponse(DESIGN_ASSETS / name, media_type="text/css")

    @app.post("/alerts/exchange")
    async def exchange(request: Request):
        payload = await command(request, Capability)
        result = await forward("POST", "/exchange", payload=payload.model_dump())
        try:
            session = Capability.model_validate(result).token
        except ValueError:
            raise HTTPException(
                503, "Alert Desk is temporarily unavailable. Try again."
            ) from None
        response = JSONResponse({"accepted": True})
        response.set_cookie(
            COOKIE,
            session,
            httponly=True,
            samesite="strict",
            max_age=GRANT_HOURS * 3600,
            path=SESSION_PATH,
            secure=public_origin.startswith("https://"),
        )
        return response

    @app.post("/alerts/findings")
    async def submit(request: Request):
        payload = await command(request, Findings)
        session = request.cookies.get(COOKIE)
        if not session:
            raise HTTPException(404, "This case or invitation is unavailable.")
        result = await forward(
            "POST",
            "/findings",
            session=session,
            payload=payload.model_dump(mode="json"),
        )
        if result != {"received": True}:
            raise HTTPException(
                503, "Alert Desk is temporarily unavailable. Try again."
            )
        return result

    @app.get("/alerts/access.js")
    def access_script():
        return FileResponse(ASSETS / "access.js", media_type="text/javascript")

    @app.get("/alerts/access")
    def access_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="access.html",
            context={"challenge": bool(request.cookies.get(CHALLENGE_COOKIE))},
        )

    @app.post("/alerts/access/challenge")
    async def request_code(request: Request):
        payload = await command(request, Capability)
        result = await forward(
            "POST", "/access/challenge", payload=payload.model_dump()
        )
        token = Capability.model_validate(result).token
        response = JSONResponse({"sent": True})
        response.set_cookie(
            CHALLENGE_COOKIE,
            token,
            httponly=True,
            samesite="strict",
            max_age=600,
            path="/alerts/access",
            secure=public_origin.startswith("https://"),
        )
        return response

    @app.post("/alerts/access/verify")
    async def verify_code(request: Request):
        if request.headers.get("origin") != public_origin:
            raise HTTPException(403, "Use the Alert Desk form.")
        raw = await bounded_json(request, 256)
        try:
            entered = json_object(raw)
            payload = MailboxCode(
                token=request.cookies.get(CHALLENGE_COOKIE, ""),
                code=entered.get("code"),
            )
        except (ValueError, TypeError):
            raise HTTPException(422, "Enter the verification code.") from None
        result = await forward("POST", "/access/verify", payload=payload.model_dump())
        token = Capability.model_validate(result).token
        response = JSONResponse({"accepted": True})
        response.delete_cookie(CHALLENGE_COOKIE, path="/alerts/access")
        response.set_cookie(
            ACCESS_COOKIE,
            token,
            httponly=True,
            samesite="strict",
            max_age=8 * 3600,
            path="/alerts",
            secure=public_origin.startswith("https://"),
        )
        return response

    @app.get("/alerts/{identifier:int}")
    async def organisation_case(request: Request, identifier: int):
        session = request.cookies.get(ACCESS_COOKIE)
        if session:
            try:
                case = await forward(
                    "GET", f"/access/alerts/{identifier}", session=session
                )
            except HTTPException as error:
                if error.status_code != 404:
                    raise
            else:
                filters = {
                    name: request.query_params[name][:100]
                    for name in ("view", "finding", "q", "before")
                    if name in request.query_params
                }
                back_url = "/alerts" + (f"?{urlencode(filters)}" if filters else "")
                return render_case(
                    request, case, organisation_case=True, back_url=back_url
                )
        return render_case(
            request,
            None,
            organisation_case=True,
            status_code=404,
            message="This alert is unavailable. If your session has expired, ask SMVS for a new invitation.",
        )

    @app.post("/alerts/{identifier:int}/findings")
    async def organisation_findings(request: Request, identifier: int):
        session = request.cookies.get(ACCESS_COOKIE)
        if not session:
            raise HTTPException(404, "Case unavailable.")
        payload = await command(request, Findings)
        result = await forward(
            "POST",
            f"/access/alerts/{identifier}/findings",
            session=session,
            payload=payload.model_dump(mode="json"),
        )
        if result.get("received") is not True:
            raise HTTPException(
                503, "Alert Desk is temporarily unavailable. Try again."
            )
        return result

    @app.get("/alerts/{identifier:int}/templates")
    async def template_library(request: Request, identifier: int):
        case = await forward("GET", f"/access/alerts/{identifier}", session=template_session(request))
        return render_template_library(request, case)

    @app.get("/alerts/templates")
    async def template_library_entry(request: Request):
        listing = await forward("GET", "/access/alerts", session=template_session(request), params={"view": "all"})
        if not listing["rows"]:
            return templates.TemplateResponse(request=request, name="comment_templates.html", context={
                "case": None, "assets": "/alerts", "my_cases_url": "/alerts", "library_active": True,
            })
        case = await forward("GET", f"/access/alerts/{listing['rows'][0]['id']}", session=template_session(request))
        # Choose an authorised context for the unchanged, case-scoped audit API.
        from starlette.responses import RedirectResponse
        query = urlencode({"return": "cases", **{k: request.query_params[k][:100] for k in ("view", "finding", "q", "before") if k in request.query_params}})
        return RedirectResponse(f"/alerts/{case['publication']}/templates?{query}", status_code=303)

    @app.get("/alerts/{identifier:int}/comment-templates")
    async def list_templates(request: Request, identifier: int):
        return await forward("GET", f"/access/alerts/{identifier}/comment-templates",
                             session=template_session(request))

    @app.get("/alerts/{identifier:int}/comment-templates/{template_id:int}")
    async def read_template(request: Request, identifier: int, template_id: int):
        return await forward("GET", f"/access/alerts/{identifier}/comment-templates/{template_id}",
                             session=template_session(request))

    def template_session(request):
        session = request.cookies.get(ACCESS_COOKIE)
        if not session:
            raise HTTPException(404, "Alert Desk access unavailable.")
        return session

    @app.post("/alerts/{identifier:int}/comment-templates")
    async def change_template(request: Request, identifier: int):
        from app.domain.investigations.comment_templates import TemplateCommand

        session = template_session(request)
        payload = await command(request, TemplateCommand, limit=8192)
        try:
            return await forward("POST", f"/access/alerts/{identifier}/comment-templates",
                                 session=session, payload=payload.model_dump())
        except HTTPException as error:
            if error.status_code == 409:
                raise HTTPException(409, "The template changed or its name is already in use. Reload the list.") from None
            raise

    return app


def local_app():
    from app.alert_desk.settings import AlertDeskSettings

    settings = AlertDeskSettings()
    settings.require_enabled()
    return create_app(
        os.environ.get("ALERT_DESK_PILOT_SECRET", ""),
        public_origin=settings.alert_desk_public_origin,
        private_origin=settings.alert_desk_private_origin,
    )
