from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db.engine import create_database_engine
from app.core.db.models import Base
from app.core.db.safety import assert_database_name_safe

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    raise RuntimeError("Offline migrations are disabled for database safety.")


def run_migrations_online() -> None:
    settings = get_settings()
    connectable = create_database_engine()

    with connectable.connect() as connection:
        selected_name = connection.execute(text("SELECT DATABASE()")).scalar_one_or_none()
        assert_database_name_safe(settings.db_name, selected_name or "")
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
