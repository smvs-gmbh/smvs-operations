from functools import lru_cache

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

