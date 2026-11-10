"""Only public-side capabilities; no database, encryption or mail credentials."""

from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.connect.protocol import canonical_origin


class ConnectSettings(BaseSettings):
    environment: str = "production"
    public_origin: str = "https://connect.smvs-gmbh.ch"
    internal_origin: str
    api_secret: SecretStr
    tally_signing_secret: SecretStr
    ca_file: str | None = None
    model_config = SettingsConfigDict(
        env_file=".env.connect",
        env_prefix="CONNECT_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def valid_boundary(self):
        for origin in (self.public_origin, self.internal_origin):
            canonical_origin(origin, self.environment == "development")
        secrets = (
            self.api_secret.get_secret_value(),
            self.tally_signing_secret.get_secret_value(),
        )
        if min(map(len, secrets)) < 32 or secrets[0] == secrets[1]:
            raise ValueError(
                "Use independent API and Tally secrets of at least 32 characters."
            )
        if self.ca_file and not Path(self.ca_file).is_file():
            raise ValueError("The internal API CA certificate is not readable.")
        return self
