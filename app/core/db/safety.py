from __future__ import annotations

from collections.abc import Callable

ALLOWED_DATABASE_NAME = "smvs_operations"


class DatabaseSafetyError(RuntimeError):
    """Raised when a schema-changing operation targets an unsafe database."""


def assert_database_name_safe(configured_name: str, selected_name: str) -> None:
    if configured_name != ALLOWED_DATABASE_NAME:
        raise DatabaseSafetyError(
            "Schema changes are enabled only for the smvs_operations database."
        )
    if selected_name != ALLOWED_DATABASE_NAME:
        raise DatabaseSafetyError(
            "The selected database is not smvs_operations; schema change refused."
        )


def assert_migration_database_safe(
    configured_name: str,
    select_database: Callable[[], str | None],
) -> None:
    selected_name = select_database()
    assert_database_name_safe(configured_name, selected_name or "")
