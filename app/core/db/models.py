from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.db.ordered_metadata import OrderedMetadataJSON


class Base(DeclarativeBase):
    pass


class IntegrationJob(Base):
    __tablename__ = "integration_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(100), nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_snapshot_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_in_past: Mapped[int | None] = mapped_column(Integer, nullable=True)
    from_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    to_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_api_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    used_api_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(String(60), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    artifacts: Mapped[list[AcquiredArtifact]] = relationship(back_populates="integration_job")


class ArtifactContent(Base):
    __tablename__ = "artifact_contents"
    __table_args__ = (UniqueConstraint("sha256", name="uq_artifact_contents_sha256"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_bytes: Mapped[bytes] = mapped_column(
        LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AcquiredArtifact(Base):
    __tablename__ = "acquired_artifacts"
    __table_args__ = (
        Index("ix_acquired_artifacts_job", "integration_job_id"),
        Index("ix_acquired_artifacts_content", "content_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_job_id: Mapped[int] = mapped_column(ForeignKey("integration_jobs.id"), nullable=False)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("artifact_contents.id", name="fk_acquired_artifacts_content"), nullable=False,
    )
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(100), nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    integration_job: Mapped[IntegrationJob] = relationship(back_populates="artifacts")
    content: Mapped[ArtifactContent] = relationship()
    processing_runs: Mapped[list[ProcessingRun]] = relationship(back_populates="artifact")

    @property
    def artifact_bytes(self) -> bytes:
        return self.content.artifact_bytes

    @property
    def sha256(self) -> str:
        return self.content.sha256

    @property
    def content_length(self) -> int:
        return self.content.content_length


class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    __table_args__ = (Index("ix_processing_runs_artifact", "artifact_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("acquired_artifacts.id"), nullable=False)
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    transform_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(String(60), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    reused_from_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id", name="fk_processing_runs_reused_from"), nullable=True,
    )

    file_metadata: Mapped[dict[str, str] | None] = mapped_column(OrderedMetadataJSON(), nullable=True)

    artifact: Mapped[AcquiredArtifact] = relationship(back_populates="processing_runs")
    datasets: Mapped[list[StagingDataset]] = relationship(back_populates="processing_run")


class StagingDataset(Base):
    __tablename__ = "staging_datasets"
    __table_args__ = (
        UniqueConstraint("processing_run_id", "source_dataset_name", name="uq_staging_dataset_run_name"),
        Index("ix_staging_datasets_artifact", "artifact_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processing_run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"), nullable=False)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("acquired_artifacts.id"), nullable=False)
    source_dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    source_headers: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    processing_run: Mapped[ProcessingRun] = relationship(back_populates="datasets")
    rows: Mapped[list[StagingRow]] = relationship(back_populates="dataset")


class StagingRow(Base):
    __tablename__ = "staging_rows"
    __table_args__ = (
        UniqueConstraint("staging_dataset_id", "source_row_number", name="uq_staging_row_source_order"),
        Index("ix_staging_rows_dataset_hash", "staging_dataset_id", "source_record_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staging_dataset_id: Mapped[int] = mapped_column(ForeignKey("staging_datasets.id"), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_row_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    dataset: Mapped[StagingDataset] = relationship(back_populates="rows")


class ImportMutex(Base):
    """Independent lock row: no foreign keys, held for an entire worker invocation."""
    __tablename__ = "import_mutexes"
    import_key: Mapped[str] = mapped_column(String(100), primary_key=True)


class ImportSchedule(Base):
    __tablename__ = "import_schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    daily_time: Mapped[str] = mapped_column(String(5), nullable=False)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ImportExecution(Base):
    __tablename__ = "import_executions"
    __table_args__ = (Index("ix_import_executions_schedule_status", "schedule_id", "status"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("import_schedules.id"), nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    integration_job_id: Mapped[int | None] = mapped_column(ForeignKey("integration_jobs.id"), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)


# Register the operational tables after integration classes are defined.
from app.domain import models as domain_models  # noqa: F401
