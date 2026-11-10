"""Internal registration settings; these never belong on SMVS Connect."""

from ipaddress import ip_address

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.connect.protocol import canonical_origin
from app.registration.crypto import cipher


class InternalRegistrationSettings(BaseSettings):
    environment: str = "production"
    connect_api_secret: SecretStr
    registration_api_allowed_ips: str = "127.0.0.1,::1"
    registration_encryption_key: SecretStr
    tally_registration_signing_secret: SecretStr
    registration_public_origin: str = "https://connect.smvs-gmbh.ch"
    registration_security_ttl_days: int = Field(7, ge=1, le=7)
    sendgrid_api_key: SecretStr | None = None
    registration_mail_template: str = "d-3cae560da6c644aa92b54d4e170b059b"
    registration_mail_from: str = "office@smvs-gmbh.ch"
    registration_mail_link_field: str = "confirmation_link"
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    @model_validator(mode="after")
    def valid_secrets(self):
        allowed = [
            item.strip()
            for item in self.registration_api_allowed_ips.split(",")
            if item.strip()
        ]
        if not allowed:
            raise ValueError("Configure the permitted Connect source IP addresses.")
        for value in allowed:
            ip_address(value)
        canonical_origin(
            self.registration_public_origin, self.environment == "development"
        )
        values = [
            self.connect_api_secret.get_secret_value(),
            self.tally_registration_signing_secret.get_secret_value(),
            self.registration_encryption_key.get_secret_value(),
        ]
        if min(map(len, values)) < 32 or len(set(values)) != len(values):
            raise ValueError("Configure independent registration secrets.")
        cipher(values[2])
        return self
