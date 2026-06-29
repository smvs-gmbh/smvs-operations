from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AccessToken:
    access_token: str
    token_type: str
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ReportType:
    report_type_id: str
    name: str
    description: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class ReportRequest:
    request_id: str
    report_type_id: str
    status: str
    created_at: datetime | None = None
    completed_at: datetime | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class DownloadedReport:
    request_id: str
    filename: str
    content_type: str | None
    local_path: Path
    size_bytes: int

