"""Read an Alert and its investigation history from the EMVO AMS Hub."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx

from app.core.config.settings import Settings
from app.core.http.sensitive import sensitive_http_request

ENDPOINTS = {
    "uat": (
        "https://amshub-uat.emvo-medicines.eu",
        "https://login.microsoftonline.com/020facb0-5e8e-4d4b-92c0-09d6e60e81ff/oauth2/v2.0/token",
        "https://uatemvoportaldirectory.onmicrosoft.com/amshub-uat/.default",
    ),
    "prd": (
        "https://amshub.emvo-medicines.eu",
        "https://login.microsoftonline.com/cfcf413f-9e93-4a10-b213-98c1cacea7f9/oauth2/v2.0/token",
        "https://prdemvoportaldirectory.onmicrosoft.com/amshub-prd/.default",
    ),
}

PARTIES = {
    "endUserInvestigationStatus": "End User",
    "mahInvestigationStatus": "MAH",
    "obpInvestigationStatus": "OBP",
    "nmvoInvestigationStatus": "NMVO",
}
ACTORS = {"enduser": "End User", "mah": "MAH", "nmvo": "NMVO", "nca": "NCA"}
STATES = {
    "UnderInvestigation": "Under investigation",
    "InvestigationPending": "Investigation pending",
    "RootCauseOnMySide": "Root cause on my side",
    "NoRootCauseOnMySide": "No root cause on my side",
}


@dataclass(frozen=True)
class Event:
    at: datetime | None
    actor: str
    organisation: str
    action: str
    reason_code: str = ""
    reason: str = ""
    message: str = ""


@dataclass(frozen=True)
class Investigation:
    state: Literal["available", "missing", "unavailable"]
    alert_status: str = ""
    parties: tuple[tuple[str, str], ...] = ()
    history: tuple[Event, ...] | None = None
    failure: str = ""


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _state(value: object) -> str:
    value = _string(value)
    if not value or value.casefold() == "blank":
        return ""
    return STATES.get(value, value)


def _timestamp(value: object) -> datetime | None:
    try:
        instant = datetime.fromisoformat(_string(value))
    except ValueError:
        return None
    return instant.astimezone(UTC) if instant.tzinfo else None


def _history(response: httpx.Response, alert_id: str) -> tuple[Event, ...]:
    data = response.json()
    if not isinstance(data, dict) or data.get("uniqueAlertId") != alert_id:
        raise ValueError("Unexpected Alert ID")
    statuses = data.get("statuses")
    actions = data.get("actions")
    if not isinstance(statuses, list) or not isinstance(actions, list):
        raise TypeError("Unexpected investigation history")
    events = []
    for row in statuses + actions:
        if not isinstance(row, dict):
            raise TypeError("Unexpected investigation entry")
        actor = _string(row.get("actor"))
        base = (
            _timestamp(row.get("timestamp")),
            ACTORS.get(actor.casefold(), actor),
            _string(row.get("organisationBusinessId")),
        )
        before = len(events)
        if (status := _state(row.get("changedStatus"))):
            events.append(Event(*base, f"Investigation status · {status}"))
        if isinstance(change := row.get("alertStatusChange"), dict):
            status = _state(change.get("newStatus"))
            events.append(
                Event(
                    *base,
                    f"Alert status · {status}" if status else "Alert status",
                    _string(change.get("reasonCode")),
                    _string(change.get("reasonText")),
                )
            )
        if isinstance(message := row.get("message"), dict):
            events.append(
                Event(*base, "Message", message=_string(message.get("messageText")))
            )
        if len(events) == before:
            events.append(Event(*base, "Unrecognised investigation event"))
    return tuple(
        sorted(
            events,
            key=lambda event: (event.at is not None, event.at or datetime.min.replace(tzinfo=UTC)),
            reverse=True,
        )
    )


def lookup(settings: Settings, alert_id: str) -> Investigation:
    """Never send credentials to a destination other than the selected EMVO environment."""
    environment = settings.ams_hub_environment
    if environment is None or not re.fullmatch(r"[A-Za-z0-9-]{1,200}", alert_id):
        return Investigation("unavailable", failure="configuration")
    prefix = f"ams_{environment}_"
    base, token_url, scope = ENDPOINTS[environment]
    endpoints = tuple(
        (getattr(settings, prefix + name) or "").removesuffix("/")
        for name in ("base_url", "token_url", "scope")
    )
    client_id = getattr(settings, prefix + "client_id")
    secret = getattr(settings, prefix + "client_secret")
    if endpoints != (base, token_url, scope) or not client_id or not secret:
        return Investigation("unavailable", failure="configuration")

    with sensitive_http_request(), httpx.Client(
        timeout=httpx.Timeout(12.0, connect=4.0),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        stage = "authentication"
        try:
            login = client.post(
                token_url,
                data={
                    "client_id": client_id,
                    "client_secret": secret.get_secret_value(),
                    "scope": scope,
                    "grant_type": "client_credentials",
                },
            )
            login.raise_for_status()
            credentials = login.json()
            token = (
                credentials.get("access_token") if isinstance(credentials, dict) else None
            )
            if not isinstance(token, str) or not token:
                return Investigation("unavailable", failure="authentication")
            headers = {"Authorization": f"Bearer {token}"}
            stage = "alert"
            response = client.get(
                f"{base}/api/v1.1/alerts/{alert_id}/details", headers=headers
            )
            if response.status_code == 404:
                return Investigation("missing")
            response.raise_for_status()
            alert = response.json()
            if not isinstance(alert, dict) or alert.get("uniqueAlertId") != alert_id:
                return Investigation("unavailable", failure="identity")
        except httpx.TimeoutException:
            return Investigation("unavailable", failure="timeout")
        except (httpx.HTTPError, ValueError, TypeError):
            return Investigation("unavailable", failure=stage)

        try:
            response = client.get(
                f"{base}/api/v1/investigations/{alert_id}/details", headers=headers
            )
            response.raise_for_status()
            history = _history(response, alert_id)
        except (httpx.HTTPError, ValueError, TypeError):
            history = None
        return Investigation(
            "available",
            _state(alert.get("status")),
            tuple((label, _state(alert.get(field))) for field, label in PARTIES.items()),
            history,
        )
