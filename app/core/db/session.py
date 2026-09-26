from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import ORMExecuteState, Session, SessionTransaction, sessionmaker

from app.core.config import get_settings
from app.core.db.engine import create_database_engine
from app.core.db.safety import (
    DatabaseSafetyError,
    assert_configured_database_safe,
    assert_database_name_safe,
)


class GuardedSession(Session):
    """Verify the actual transaction connection before runtime SQL is issued."""

    def __init__(self, *args: object, configured_database: str | None = None, **kwargs: object) -> None:
        self.configured_database = (
            get_settings().db_name if configured_database is None else configured_database
        )
        assert_configured_database_safe(self.configured_database)
        self.safety_failed = False
        super().__init__(*args, **kwargs)

    def get_bind(self, *args: object, **kwargs: object):
        require_runtime_session(self)
        return super().get_bind(*args, **kwargs)


def require_runtime_session(session: Session) -> None:
    if not isinstance(session, GuardedSession) or session.safety_failed:
        raise DatabaseSafetyError("A verified runtime database session is required.")


@event.listens_for(GuardedSession, "after_begin")
def _verify_transaction(session: GuardedSession, transaction: SessionTransaction, connection: Connection) -> None:
    require_runtime_session(session)
    try:
        selected = connection.execute(text("SELECT DATABASE()")).scalar_one_or_none()
        assert_database_name_safe(session.configured_database, selected or "")
    except Exception:  # noqa: BLE001 - every verification failure must deny access
        session.safety_failed = True
        # Driver errors can contain connection details. Do not propagate them.
        raise DatabaseSafetyError("Runtime database verification failed; access refused.") from None


@event.listens_for(GuardedSession, "do_orm_execute")
def _reject_poisoned_execution(state: ORMExecuteState) -> None:
    require_runtime_session(state.session)


@event.listens_for(GuardedSession, "before_flush")
def _reject_poisoned_flush(session: GuardedSession, *args: object) -> None:
    require_runtime_session(session)


@event.listens_for(GuardedSession, "before_commit")
def _reject_poisoned_commit(session: GuardedSession) -> None:
    require_runtime_session(session)


@lru_cache
def get_session_factory() -> sessionmaker[GuardedSession]:
    settings = get_settings()
    assert_configured_database_safe(settings.db_name)
    return sessionmaker(
        bind=create_database_engine(),
        class_=GuardedSession,
        configured_database=settings.db_name,
        autoflush=False,
        expire_on_commit=False,
    )


def SessionFactory() -> GuardedSession:
    return get_session_factory()()


def get_session() -> Iterator[GuardedSession]:
    with SessionFactory() as session:
        yield session
