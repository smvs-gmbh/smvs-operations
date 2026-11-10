"""Encrypted receipt fields and legacy buffered mapping; direct receipts live internally."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class IntakeBase(DeclarativeBase):
    pass


class ReceiptColumns:
    """Shared encrypted receipt fields; mapped separately for each storage mode."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True)
    submission_id: Mapped[str] = mapped_column(String(100), unique=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    # Both contact details and security answers are encrypted in the intake store.
    payload_ciphertext: Mapped[str | None] = mapped_column(Text)
    token_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    token_ciphertext: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    acknowledged_revision: Mapped[int] = mapped_column(Integer, default=0)
    mail_status: Mapped[str] = mapped_column(String(30), default="queued")
    mail_attempts: Mapped[int] = mapped_column(Integer, default=0)
    mail_attempted_at: Mapped[datetime | None] = mapped_column(DateTime)
    mail_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Optimistic version is separate from the exchange revision.
    version: Mapped[int] = mapped_column(Integer, default=1)

    @declared_attr.directive
    def __mapper_args__(cls):
        return {"version_id_col": cls.version}


class IntakeRegistration(ReceiptColumns, IntakeBase):
    """Legacy buffered-intake mapping, retained for existing local tests."""

    __tablename__ = "registrations"
