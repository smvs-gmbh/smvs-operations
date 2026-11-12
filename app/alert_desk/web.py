"""Stateless local browser gateway for SMVS Alert Desk."""

import os
from pathlib import Path
from urllib.parse import urlencode
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
from app.connect.protocol import PRIVATE_HEADERS, bounded_json, json_object

ASSETS = Path(__file__).parent
DESIGN_ASSETS = ASSETS.parent / "connect_preview" / "assets"
ACCESS_COOKIE = "alert_desk_access"
CHALLENGE_COOKIE = "alert_desk_mailbox_check"
DESIGN_STYLES = {"focused.css", "compact.css", "columns.css"}
templates = Jinja2Templates(directory=str(ASSETS))


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
):
    return templates.TemplateResponse(
        request=request,
        name="case.html",
        status_code=status_code,
        context={
            "case": case,
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
        },
    )


def create_app(secret, *, transport=None):
    if len(secret) < 32:
        raise ValueError(
            "Set a dedicated Alert Desk pilot secret of at least 32 characters."
        )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def protect(request, call_next):
        if (
            request.headers.get("host") != PUBLIC_ORIGIN.removeprefix("http://")
            or not request.client
            or request.client.host not in {"127.0.0.1", "::1"}
        ):
            return HTMLResponse(
                "Use the local Alert Desk address.", 403, headers=PRIVATE_HEADERS
            )
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
                    PRIVATE_ORIGIN + path,
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

    async def command(request, schema):
        if request.headers.get("origin") != PUBLIC_ORIGIN:
            raise HTTPException(403, "Use the Alert Desk form.")
        raw = await bounded_json(request, 4096)
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

    @app.get("/alerts/portal.css")
    def portal_stylesheet():
        return FileResponse(
            ASSETS.parent / "portal" / "static" / "portal.css", media_type="text/css"
        )

    @app.get("/alerts/case.css")
    def stylesheet():
        return FileResponse(ASSETS / "case.css", media_type="text/css")

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
            secure=PUBLIC_ORIGIN.startswith("https://"),
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
            secure=PUBLIC_ORIGIN.startswith("https://"),
        )
        return response

    @app.post("/alerts/access/verify")
    async def verify_code(request: Request):
        if request.headers.get("origin") != PUBLIC_ORIGIN:
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
            secure=PUBLIC_ORIGIN.startswith("https://"),
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

    return app


def local_app():
    return create_app(os.environ.get("ALERT_DESK_PILOT_SECRET", ""))
