from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SMVS Operations"
    environment: str = "development"
    log_level: str = "INFO"
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str

    nmvs_reporting_base_url: str | None = None
    nmvs_token_url: str | None = None
    nmvs_client_id: str | None = None
    nmvs_client_secret: SecretStr | None = None
    nmvs_scope: str | None = None
    nmvs_api_version: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

