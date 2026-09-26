import pytest

from app.core.db.safety import DatabaseSafetyError, assert_database_name_safe


def test_allows_only_the_application_database() -> None:
    assert_database_name_safe("smvs_operations", "smvs_operations")


@pytest.mark.parametrize(
    ("configured", "selected"),
    [
        ("smvs", "smvs"),
        ("smvs", "smvs_operations"),
        ("smvs_operations", "smvs"),
        ("", "smvs_operations"),
        ("smvs_operations", ""),
    ],
)
def test_rejects_unsafe_database_selection(configured: str, selected: str) -> None:
    with pytest.raises(DatabaseSafetyError):
        assert_database_name_safe(configured, selected)
