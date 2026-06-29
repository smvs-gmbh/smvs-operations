from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.http import HttpClient


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    token_type: str
    expires_at: datetime | None = None

    def is_expired(self, safety_margin_seconds: int = 60) -> bool:
        if self.expires_at is None:
            return False

        return datetime.now(UTC) + timedelta(seconds=safety_margin_seconds) >= self.expires_at


class OAuthClient:
    def __init__(self, http_client: HttpClient) -> None:
        self._http_client = http_client

    def get_client_credentials_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
    ) -> OAuthToken:
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

        if scope:
            data["scope"] = scope

        response = self._http_client.post(
            token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=data,
        )

        payload = response.json()

        expires_at = None
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, int):
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        return OAuthToken(
            access_token=payload["access_token"],
            token_type=payload.get("token_type", "Bearer"),
            expires_at=expires_at,
        )
