from __future__ import annotations

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.core.db.safety import assert_migration_database_safe


def build_database_url() -> URL:
    settings = get_settings()
    return URL.create(
        drivername="mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


def create_database_engine() -> Engine:
    return create_engine(build_database_url(), pool_pre_ping=True)


def assert_engine_database_safe(engine: Engine) -> None:
    settings = get_settings()
    with engine.connect() as connection:
        selected_name = connection.execute(text("SELECT DATABASE()")).scalar_one_or_none()
    assert_migration_database_safe(settings.db_name, lambda: selected_name)
