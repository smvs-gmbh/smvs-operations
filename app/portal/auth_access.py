"""Enforce internal portal roles before routing requests."""

from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.core.db.session import SessionFactory
from app.domain.auth import service as auth
from app.domain.models import PortalUser

PUBLIC_AUTH = {
    ("GET", "/auth/login"),
    ("POST", "/auth/enrol/options"),
    ("POST", "/auth/enrol/finish"),
    ("POST", "/auth/signin/options"),
    ("POST", "/auth/signin/finish"),
}


def principal(raw):
    if not raw:
        return None
    with SessionFactory() as session:
        token = auth.get_token(session, raw, "session")
        user = session.get(PortalUser, token.user_id) if token else None
        return user if user and not user.disabled_at else None


def in_section(path, section):
    return path == section or path.startswith(section + "/")


def install_portal_access(app, settings):
    if settings.portal_auth_enabled:
        auth.origin_config(settings)
    elif settings.environment != "development":
        raise RuntimeError("Enable portal authentication outside development.")

    @app.middleware("http")
    async def portal_access(request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        request.state.portal_auth_enabled = settings.portal_auth_enabled
        if path == "/health":
            return await call_next(request)
        if not settings.portal_auth_enabled:
            if (
                request.url.hostname not in {"localhost", "127.0.0.1", "::1"}
                or not request.client
                or request.client.host not in {"127.0.0.1", "::1"}
            ):
                return PlainTextResponse(
                    "The unauthenticated preview is available on loopback only.", 403
                )
            if in_section(path, "/admin") or in_section(path, "/auth"):
                return PlainTextResponse("Portal authentication is disabled.", 404)
            return await call_next(request)
        if request.headers.get("host") != urlsplit(settings.portal_auth_origin).netloc:
            return PlainTextResponse("Use the configured portal address.", 403)
        if in_section(path, "/portal-static") or (request.method, path) in PUBLIC_AUTH:
            return await call_next(request)
        user = await run_in_threadpool(
            principal, request.cookies.get(auth.SESSION_COOKIE)
        )
        if user is None:
            if request.method == "GET":
                return RedirectResponse(
                    "/auth/login",
                    status_code=303,
                    headers={"Cache-Control": "no-store"},
                )
            return PlainTextResponse("Sign in to continue.", 401)
        request.state.portal_user = user
        if path == "/" and not user.is_nmvo:
            return RedirectResponse("/admin/users", status_code=303)
        if path != "/user-guide" and not in_section(path, "/auth"):
            admin_section = any(
                in_section(path, section)
                for section in ("/admin", "/imports", "/intelligence")
            )
            if not (user.is_admin if admin_section else user.is_nmvo):
                return PlainTextResponse(
                    "This role cannot access the requested page.", 403
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response
