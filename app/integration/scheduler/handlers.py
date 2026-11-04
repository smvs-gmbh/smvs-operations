import httpx

from app.core.config import get_settings
from app.core.db.session import SessionFactory
from app.core.http.sensitive import sensitive_http_request
from app.integration.sources.nmvs.daily_snapshot import DailySnapshotAcquisition
from app.integration.sources.nmvs.download_uri import validate_report_base_url
from app.integration.sources.nmvs.reporting import ReportingApiClient
from app.integration.sources.sai.acquisition import SAIAcquisition
from app.integration.sources.sai.client import SAIClient


def import_sai():
    client = SAIClient()
    try:
        with SessionFactory() as session:
            return SAIAcquisition(client).run(session)
    finally:
        client.close()


def import_daily_snapshot():
    settings = get_settings()
    if not all(
        (
            settings.nmvs_reporting_base_url,
            settings.nmvs_token_url,
            settings.nmvs_client_id,
            settings.nmvs_client_secret,
        )
    ):
        raise ValueError("NMVS reporting credentials are not configured.")
    validate_report_base_url(settings.nmvs_token_url)
    validate_report_base_url(settings.nmvs_reporting_base_url)

    def token():
        data = {
            "grant_type": "client_credentials",
            "client_id": settings.nmvs_client_id,
            "client_secret": settings.nmvs_client_secret.get_secret_value(),
        }
        if settings.nmvs_scope:
            data["scope"] = settings.nmvs_scope
        with sensitive_http_request():
            try:
                response = httpx.post(
                    settings.nmvs_token_url,
                    data=data,
                    timeout=30,
                    follow_redirects=False,
                )
                if response.status_code != 200:
                    raise ValueError("NMVS authentication failed.")
                value = response.json().get("access_token")
                if not isinstance(value, str) or not value:
                    raise ValueError("NMVS authentication failed.")
                return value
            except (httpx.HTTPError, ValueError):
                raise ValueError("NMVS authentication failed.") from None

    client = ReportingApiClient(
        settings.nmvs_reporting_base_url,
        token_provider=token,
        api_version=settings.nmvs_api_version,
    )
    try:
        with SessionFactory() as session:
            return DailySnapshotAcquisition(client).run(session)
    finally:
        client.close()


def default_handlers():
    # Register additional source runners here; the scheduler remains independent
    # of source protocols, credentials and parsing logic.
    return {"sai": import_sai, "daily_snapshot": import_daily_snapshot}
