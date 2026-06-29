from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ImportResult:
    source_name: str
    channel_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    records_processed: int | None = None
    message: str | None = None


class InformationSource(ABC):
    """Base class for an authoritative Operational Information Source."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> bool:
        raise NotImplementedError


class ImportChannel(ABC):
    """Base class for a technical import channel of an Information Source."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def run(self) -> ImportResult:
        raise NotImplementedError


def started_import(source_name: str, channel_name: str) -> ImportResult:
    return ImportResult(
        source_name=source_name,
        channel_name=channel_name,
        status="running",
        started_at=datetime.now(UTC),
    )
