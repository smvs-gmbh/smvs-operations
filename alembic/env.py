from logging.config import fileConfig

from sqlalchemy import text

from alembic import context
from app.core.config import get_settings
from app.core.db.engine import create_database_engine
from app.core.db.models import Base
from app.core.db.safety import (
    assert_configured_database_safe,
    assert_database_name_safe,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    raise RuntimeError("Offline migrations are disabled for database safety.")


def run_migrations_online() -> None:
    settings = get_settings()
    assert_configured_database_safe(settings.db_name)
    connectable = create_database_engine()

    with connectable.begin() as connection:
        selected_name = connection.execute(text("SELECT DATABASE()")).scalar_one_or_none()
        assert_database_name_safe(settings.db_name, selected_name or "")
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
