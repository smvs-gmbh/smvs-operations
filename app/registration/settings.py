"""Intake configuration does not load the Operations DB or NMVS credentials."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class IntakeSettings(BaseSettings):
    registration_environment: str = "development"
    registration_database_url: SecretStr
    registration_public_origin: str = "http://localhost:8013"
    registration_encryption_key: SecretStr
    registration_exchange_secret: SecretStr
    tally_registration_signing_secret: SecretStr
    sendgrid_api_key: SecretStr | None = None
    registration_mail_template: str = "d-3cae560da6c644aa92b54d4e170b059b"
    registration_mail_from: str = ""
    registration_mail_link_field: str = ""
    registration_security_ttl_days: int = Field(7, ge=1, le=30)
    model_config = SettingsConfigDict(
        env_file=".env.registration-intake", extra="ignore"
    )
