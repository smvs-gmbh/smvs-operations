from __future__ import annotations

from collections.abc import Callable

ALLOWED_DATABASE_NAME = "smvs_operations"


class DatabaseSafetyError(RuntimeError):
    """Raised when database access cannot be verified as safe."""


def assert_configured_database_safe(configured_name: str) -> None:
    if configured_name != ALLOWED_DATABASE_NAME:
        raise DatabaseSafetyError(
            "Database access is enabled only for smvs_operations."
        )


def assert_database_name_safe(configured_name: str, selected_name: str) -> None:
    assert_configured_database_safe(configured_name)
    if selected_name != ALLOWED_DATABASE_NAME:
        raise DatabaseSafetyError(
            "The selected database is not smvs_operations; access refused."
        )


def assert_migration_database_safe(
    configured_name: str,
    select_database: Callable[[], str | None],
) -> None:
    assert_configured_database_safe(configured_name)
    selected_name = select_database()
    assert_database_name_safe(configured_name, selected_name or "")
