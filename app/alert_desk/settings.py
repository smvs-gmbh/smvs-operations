"""Explicit hosted TEST configuration; private API stays on the same node."""

from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.alert_desk.schema import PRIVATE_ORIGIN, PUBLIC_ORIGIN


class AlertDeskSettings(BaseSettings):
    environment: str = "development"
    alert_desk_test_enabled: bool = False
    alert_desk_public_origin: str = PUBLIC_ORIGIN
    alert_desk_private_origin: str = PRIVATE_ORIGIN

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_origins(self):
        for origin, private in (
            (self.alert_desk_public_origin, False),
            (self.alert_desk_private_origin, True),
        ):
            url = urlsplit(origin)
            local = url.hostname in {"localhost", "127.0.0.1", "::1"}
            try:
                port = url.port
            except ValueError:
                raise ValueError("Invalid Alert Desk origin port.") from None
            if (
                not url.hostname
                or url.username
                or url.password
                or url.path
                or url.query
                or url.fragment
                or origin != f"{url.scheme}://{url.netloc}"
                or url.scheme not in {"http", "https"}
                or (url.scheme == "http" and not local)
                or (private and (not local or url.scheme != "http"))
                or port == 0
            ):
                raise ValueError(
                    "Use a canonical HTTPS participant origin and a loopback private API."
                )
        return self

    def require_enabled(self):
        if self.environment != "development" and not (
            self.environment == "test" and self.alert_desk_test_enabled
        ):
            raise RuntimeError("Alert Desk is disabled in this environment.")


def mail_origin():
    settings = AlertDeskSettings()
    settings.require_enabled()
    return settings.alert_desk_public_origin
