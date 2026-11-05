"""Explicit Reporting API settings; supports the existing PROD environment names."""

import time

import httpx

from app.core.config import get_settings
from app.core.http.sensitive import sensitive_http_request
from app.integration.sources.nmvs.download_uri import (
    validate_download_uri,
    validate_report_base_url,
)
from app.integration.sources.nmvs.reporting import ReportingApiClient

_DEFAULT_VERSION = object()


def reporting_client(
    client_class=ReportingApiClient, *, base_url=None, api_version=_DEFAULT_VERSION
):
    settings = get_settings()
    base = base_url or settings.nmvs_reporting_base_url
    if not base or not settings.nmvs_client_id or not settings.nmvs_client_secret:
        raise ValueError("NMVS reporting credentials are not configured.")
    validate_report_base_url(base)
    cached = {}

    def token():
        if cached.get("until", 0) > time.monotonic():
            return cached["token"]
        with (
            sensitive_http_request(),
            httpx.Client(timeout=30, follow_redirects=False) as http,
        ):
            try:
                endpoint = settings.nmvs_token_url
                if not endpoint:
                    identity = settings.nmvs_identity_base_url
                    if not identity:
                        raise ValueError("NMVS identity URL is missing.")
                    validate_report_base_url(identity)
                    response = http.get(
                        identity.rstrip("/") + "/.well-known/openid-configuration"
                    )
                    response.raise_for_status()
                    endpoint = validate_download_uri(
                        response.json()["token_endpoint"], identity
                    )
                validate_report_base_url(endpoint)
                data = {
                    "grant_type": "client_credentials",
                    "client_id": settings.nmvs_client_id,
                    "client_secret": settings.nmvs_client_secret.get_secret_value(),
                }
                if settings.nmvs_scope:
                    data["scope"] = settings.nmvs_scope
                response = http.post(endpoint, data=data)
                response.raise_for_status()
                payload = response.json()
                value = payload.get("access_token")
                if not isinstance(value, str) or not value:
                    raise ValueError("NMVS authentication failed.")
                cached.update(
                    token=value,
                    until=time.monotonic()
                    + max(0, int(payload.get("expires_in", 0)) - 60),
                )
                return value
            except Exception:  # noqa: BLE001 - sanitize credentials and source/SQL diagnostics
                raise ValueError("NMVS authentication failed.") from None

    client = client_class(
        base,
        token_provider=token,
        api_version=settings.nmvs_api_version
        if api_version is _DEFAULT_VERSION
        else api_version,
    )
    client.language = settings.nmvs_language
    client.user_agent = settings.nmvs_user_agent
    return client
