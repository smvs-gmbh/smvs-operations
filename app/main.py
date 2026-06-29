import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health_check() -> dict[str, str]:
    logger.info("Health check requested")
    return {
        "status": "ok",
        "environment": settings.environment,
    }

