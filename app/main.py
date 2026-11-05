import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.portal.auth_access import install_portal_access
from app.portal.auth_routes import router as auth_router
from app.portal.participant_routes import router as participant_router
from app.portal.routes import router as portal_router
from app.portal.activity_routes import router as activity_router
from app.portal.exception_routes import router as exception_router
from app.portal.pack_audit_routes import router as pack_audit_router
from app.portal.upload_routes import router as upload_router
from app.portal.intelligence_routes import router as intelligence_router
from app.portal.mah_report_routes import router as mah_report_router
from app.portal.crm_routes import router as crm_router
from app.portal.import_routes import router as import_router

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None, openapi_url=None)
install_portal_access(app, settings)
app.include_router(auth_router)
app.mount(
    "/portal-static",
    StaticFiles(directory=str(Path(__file__).parent / "portal/static")),
    name="portal_static",
)
app.include_router(portal_router)
app.include_router(participant_router)
app.include_router(activity_router)
app.include_router(exception_router)
app.include_router(pack_audit_router)
app.include_router(upload_router)
app.include_router(import_router)
app.include_router(intelligence_router)
app.include_router(mah_report_router)
app.include_router(crm_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    logger.info("Health check requested")
    return {
        "status": "ok",
        "environment": settings.environment,
    }
