from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SMVS Operations"
    environment: str = "development"
    log_level: str = "INFO"
    alert_desk_test_enabled: bool = False
    portal_auth_enabled: bool = False
    portal_auth_origin: str = "http://localhost:8010"
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str
    db_ssl_ca: str | None = None
    db_ssl_server_cert_sha256: str | None = None
    db_ssl_legacy_certificate: bool = False

    nmvs_reporting_base_url: str | None = Field(
        None,
        validation_alias=AliasChoices(
            "NMVS_REPORTING_BASE_URL", "NMVS_PROD_REPORT_BASE_URL"
        ),
    )
    nmvs_identity_base_url: str | None = Field(
        None,
        validation_alias=AliasChoices(
            "NMVS_IDENTITY_BASE_URL_OVERRIDE", "NMVS_PROD_IDENTITY_BASE_URL"
        ),
    )
    nmvs_language: str = "en"
    nmvs_user_agent: str = "SMVS Operations"
    nmvs_token_url: str | None = None
    nmvs_client_id: str | None = Field(
        None, validation_alias=AliasChoices("NMVS_CLIENT_ID", "NMVS_PROD_CLIENT_ID")
    )
    nmvs_client_secret: SecretStr | None = Field(
        None,
        validation_alias=AliasChoices("NMVS_CLIENT_SECRET", "NMVS_PROD_CLIENT_SECRET"),
    )
    nmvs_exceptions_base_url: str | None = None
    nmvs_exceptions_api_version: str | None = None
    nmvs_exceptions_authority: str | None = None
    nmvs_scope: str | None = None
    nmvs_api_version: str | None = None
    ams_hub_environment: Literal["uat", "prd"] | None = None
    ams_uat_base_url: str | None = None
    ams_uat_token_url: str | None = None
    ams_uat_scope: str | None = None
    ams_uat_client_id: str | None = None
    ams_uat_client_secret: SecretStr | None = None
    ams_prd_base_url: str | None = None
    ams_prd_token_url: str | None = None
    ams_prd_scope: str | None = None
    ams_prd_client_id: str | None = None
    ams_prd_client_secret: SecretStr | None = None
    logo_dev_publishable_key: str | None = None
    openai_api_key: SecretStr | None = None
    openai_search_model: str | None = None
    openai_web_model: str | None = None
    declaration_invitation_secret: SecretStr | None = None
    registration_delivery_mode: str = "buffered"
    connect_api_secret: SecretStr | None = None
    registration_intake_url: str | None = None
    registration_exchange_secret: SecretStr | None = None
    registration_encryption_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
