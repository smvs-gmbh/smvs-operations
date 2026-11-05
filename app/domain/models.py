from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.models import Base

DOMAIN_TABLES = {
    "mapping_runs",
    "current_publications",
    "products",
    "product_source_records",
    "product_versions",
    "batches",
    "sai_holders",
    "sai_preparations",
    "sai_packages",
    "product_reference_matches",
}


def evidence_row():
    return mapped_column(
        ForeignKey("staging_rows.id", ondelete="SET NULL"), nullable=True
    )


class MappingRun(Base):
    __tablename__ = "mapping_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    input_key: Mapped[str] = mapped_column(String(64), unique=True)
    snapshot_run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"))
    sai_run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"))
    source_namespace: Mapped[str] = mapped_column(String(255))
    mapping_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40))
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    statistics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    failure_message: Mapped[str | None] = mapped_column(Text)


class CurrentPublication(Base):
    __tablename__ = "current_publications"
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    mapping_run_id: Mapped[int] = mapped_column(ForeignKey("mapping_runs.id"))
    source_namespace: Mapped[str] = mapped_column(String(255))
    snapshot_date: Mapped[date] = mapped_column(Date)
    sai_exported_at: Mapped[datetime] = mapped_column(DateTime)
    published_at: Mapped[datetime] = mapped_column(DateTime)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(64), unique=True)
    gtin14: Mapped[str | None] = mapped_column(String(14), unique=True)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime)


class ProductSourceRecord(Base):
    __tablename__ = "product_source_records"
    __table_args__ = (
        Index(
            "ix_product_sources_namespace_observed", "source_namespace", "is_observed"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), unique=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    source_namespace: Mapped[str] = mapped_column(String(255))
    code_scheme: Mapped[str] = mapped_column(String(100))
    source_code: Mapped[str] = mapped_column(String(100))
    reported_version: Mapped[int | None] = mapped_column(Integer)
    reported_version_text: Mapped[str] = mapped_column(String(100))
    product_state: Mapped[str | None] = mapped_column(String(100))
    pack_count: Mapped[int | None] = mapped_column(BigInteger)
    active_pack_count: Mapped[int | None] = mapped_column(BigInteger)
    is_observed: Mapped[int] = mapped_column(Integer)
    last_mapping_run_id: Mapped[int] = mapped_column(ForeignKey("mapping_runs.id"))
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


class ProductVersion(Base):
    __tablename__ = "product_versions"
    __table_args__ = (Index("ix_product_versions_source", "product_source_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    version_key: Mapped[str] = mapped_column(String(64), unique=True)
    product_source_id: Mapped[int] = mapped_column(
        ForeignKey("product_source_records.id")
    )
    version_number: Mapped[int | None] = mapped_column(Integer)
    source_version_value: Mapped[str] = mapped_column(String(100))
    detail_status: Mapped[str] = mapped_column(String(40))
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    last_mapping_run_id: Mapped[int] = mapped_column(ForeignKey("mapping_runs.id"))


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (
        Index("ix_batches_product_observed", "product_source_id", "is_observed"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_key: Mapped[str] = mapped_column(String(64), unique=True)
    product_source_id: Mapped[int] = mapped_column(
        ForeignKey("product_source_records.id")
    )
    product_version_id: Mapped[int] = mapped_column(ForeignKey("product_versions.id"))
    batch_code: Mapped[str] = mapped_column(String(100))
    expiry_source_text: Mapped[str | None] = mapped_column(String(100))
    batch_state: Mapped[str | None] = mapped_column(String(100))
    pack_count: Mapped[int | None] = mapped_column(BigInteger)
    active_pack_count: Mapped[int | None] = mapped_column(BigInteger)
    is_observed: Mapped[int] = mapped_column(Integer)
    last_mapping_run_id: Mapped[int] = mapped_column(ForeignKey("mapping_runs.id"))
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


class SAIHolder(Base):
    __tablename__ = "sai_holders"
    id: Mapped[int] = mapped_column(primary_key=True)
    holder_key: Mapped[str] = mapped_column(String(64), unique=True)
    partner_number: Mapped[str] = mapped_column(String(100))
    company_name: Mapped[str | None] = mapped_column(Text)
    gln: Mapped[str | None] = mapped_column(String(100))
    is_observed: Mapped[int] = mapped_column(Integer)
    last_mapping_run_id: Mapped[int] = mapped_column(ForeignKey("mapping_runs.id"))
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


class SAIPreparation(Base):
    __tablename__ = "sai_preparations"
    id: Mapped[int] = mapped_column(primary_key=True)
    preparation_key: Mapped[str] = mapped_column(String(64), unique=True)
    approval_number: Mapped[str] = mapped_column(String(100))
    preparation_name: Mapped[str | None] = mapped_column(Text)
    holder_id: Mapped[int | None] = mapped_column(ForeignKey("sai_holders.id"))
    atc_code: Mapped[str | None] = mapped_column(String(100))
    approval_status: Mapped[str | None] = mapped_column(String(100))
    is_observed: Mapped[int] = mapped_column(Integer)
    last_mapping_run_id: Mapped[int] = mapped_column(ForeignKey("mapping_runs.id"))
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


class SAIPackage(Base):
    __tablename__ = "sai_packages"
    __table_args__ = (Index("ix_sai_packages_gtin_observed", "gtin14", "is_observed"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    package_key: Mapped[str] = mapped_column(String(64), unique=True)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("sai_preparations.id"))
    sequence_number: Mapped[str] = mapped_column(String(100))
    package_code: Mapped[str] = mapped_column(String(100))
    source_gtin: Mapped[str | None] = mapped_column(String(100))
    gtin14: Mapped[str | None] = mapped_column(String(14))
    description_de: Mapped[str | None] = mapped_column(Text)
    description_fr: Mapped[str | None] = mapped_column(Text)
    approval_status: Mapped[str | None] = mapped_column(String(100))
    is_observed: Mapped[int] = mapped_column(Integer)
    last_mapping_run_id: Mapped[int] = mapped_column(ForeignKey("mapping_runs.id"))
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


class ProductReferenceMatch(Base):
    __tablename__ = "product_reference_matches"
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    sai_package_id: Mapped[int | None] = mapped_column(ForeignKey("sai_packages.id"))
    match_status: Mapped[str] = mapped_column(String(40), index=True)
    match_reason: Mapped[str] = mapped_column(String(100))
    last_mapping_run_id: Mapped[int] = mapped_column(ForeignKey("mapping_runs.id"))


PARTICIPANT_TABLES = {
    "participant_mapping_runs",
    "participant_publications",
    "local_organisations",
    "local_locations",
}
DOMAIN_TABLES.update(PARTICIPANT_TABLES)


class ParticipantMappingRun(Base):
    __tablename__ = "participant_mapping_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    input_key: Mapped[str] = mapped_column(String(64), unique=True)
    snapshot_run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"))
    source_namespace: Mapped[str] = mapped_column(String(255))
    mapping_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40))
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    statistics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    failure_message: Mapped[str | None] = mapped_column(Text)


class ParticipantPublication(Base):
    __tablename__ = "participant_publications"
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    mapping_run_id: Mapped[int] = mapped_column(
        ForeignKey("participant_mapping_runs.id")
    )
    source_namespace: Mapped[str] = mapped_column(String(255))
    snapshot_date: Mapped[date] = mapped_column(Date)
    published_at: Mapped[datetime] = mapped_column(DateTime)


class LocalOrganisation(Base):
    __tablename__ = "local_organisations"
    __table_args__ = (
        Index("ix_local_org_namespace_observed", "source_namespace", "is_observed"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), unique=True)
    source_namespace: Mapped[str] = mapped_column(String(255))
    source_organisation_id: Mapped[str] = mapped_column(String(100))
    organisation_name: Mapped[str | None] = mapped_column(Text)
    organisation_type: Mapped[str | None] = mapped_column(String(100))
    organisation_subtype: Mapped[str | None] = mapped_column(String(100))
    organisation_status: Mapped[str | None] = mapped_column(String(100))
    creation_date_text: Mapped[str | None] = mapped_column(Text)
    registration_date_text: Mapped[str | None] = mapped_column(Text)
    expiry_date_text: Mapped[str | None] = mapped_column(Text)
    is_observed: Mapped[int] = mapped_column(Integer)
    last_participant_run_id: Mapped[int] = mapped_column(
        ForeignKey("participant_mapping_runs.id")
    )
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


class LocalLocation(Base):
    __tablename__ = "local_locations"
    __table_args__ = (
        Index(
            "ix_local_location_namespace_observed", "source_namespace", "is_observed"
        ),
        Index("ix_local_location_org_observed", "organisation_id", "is_observed"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), unique=True)
    source_namespace: Mapped[str] = mapped_column(String(255))
    source_location_id: Mapped[str] = mapped_column(String(100))
    source_organisation_id: Mapped[str | None] = mapped_column(String(100))
    organisation_id: Mapped[int | None] = mapped_column(
        ForeignKey("local_organisations.id")
    )
    organisation_link_status: Mapped[str] = mapped_column(String(40))
    location_name: Mapped[str | None] = mapped_column(Text)
    location_status: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(100))
    legitimacy_information: Mapped[str | None] = mapped_column(Text)
    equipment_count: Mapped[int | None] = mapped_column(BigInteger)
    creation_date_text: Mapped[str | None] = mapped_column(Text)
    is_observed: Mapped[int] = mapped_column(Integer)
    last_participant_run_id: Mapped[int] = mapped_column(
        ForeignKey("participant_mapping_runs.id")
    )
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


ACTIVITY_TABLES = {"activity_publications", "activity_days", "activity_facts"}
DOMAIN_TABLES.update(ACTIVITY_TABLES)


class ActivityPublication(Base):
    """Acceptance of an immutable extracted report, independent from acquisition."""

    __tablename__ = "activity_publications"
    id: Mapped[int] = mapped_column(primary_key=True)
    input_key: Mapped[str] = mapped_column(String(64), unique=True)
    processing_run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"))
    source_namespace: Mapped[str] = mapped_column(String(255))
    mapping_version: Mapped[str] = mapped_column(String(100))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    source_requested_at: Mapped[datetime] = mapped_column(DateTime)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    statistics: Mapped[dict[str, Any]] = mapped_column(JSON)


class ActivityDay(Base):
    """Complete published coverage, including sections with no activity rows."""

    __tablename__ = "activity_days"
    __table_args__ = (
        Index("ix_activity_day_namespace_date", "source_namespace", "activity_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    day_key: Mapped[str] = mapped_column(String(64), unique=True)
    source_namespace: Mapped[str] = mapped_column(String(255))
    section: Mapped[str] = mapped_column(String(40))
    activity_date: Mapped[date] = mapped_column(Date)
    publication_id: Mapped[int] = mapped_column(ForeignKey("activity_publications.id"))


class ActivityFact(Base):
    __tablename__ = "activity_facts"
    __table_args__ = (
        Index("ix_activity_fact_namespace_date", "source_namespace", "activity_date"),
        Index(
            "ix_activity_fact_organisation",
            "source_namespace",
            "source_organisation_id",
            "activity_date",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    fact_key: Mapped[str] = mapped_column(String(64), unique=True)
    source_namespace: Mapped[str] = mapped_column(String(255))
    section: Mapped[str] = mapped_column(String(40))
    activity_date: Mapped[date] = mapped_column(Date)
    source_organisation_id: Mapped[str | None] = mapped_column(String(100))
    organisation_name: Mapped[str | None] = mapped_column(Text)
    organisation_type: Mapped[str] = mapped_column(String(100))
    market: Mapped[str | None] = mapped_column(String(100))
    business_process: Mapped[str] = mapped_column(String(255))
    metric_kind: Mapped[str] = mapped_column(String(40))
    metric_value: Mapped[Decimal] = mapped_column(Numeric(35, 15))
    transaction_count: Mapped[int] = mapped_column(BigInteger)
    exception_count: Mapped[int] = mapped_column(BigInteger)
    publication_id: Mapped[int] = mapped_column(ForeignKey("activity_publications.id"))
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


EXCEPTION_TABLES = {"exception_publications", "nmvs_exceptions", "exception_revisions"}
DOMAIN_TABLES.update(EXCEPTION_TABLES)


class ExceptionPublication(Base):
    __tablename__ = "exception_publications"
    id: Mapped[int] = mapped_column(primary_key=True)
    input_key: Mapped[str] = mapped_column(String(64), unique=True)
    processing_run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"))
    source_namespace: Mapped[str] = mapped_column(String(255))
    mapping_version: Mapped[str] = mapped_column(String(100))
    period_start: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    query_started_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    statistics: Mapped[dict[str, Any]] = mapped_column(JSON)


class NMVSException(Base):
    __tablename__ = "nmvs_exceptions"
    __table_args__ = (
        Index("ix_exceptions_namespace_date", "source_namespace", "alert_at"),
        Index(
            "ix_exceptions_product_serial",
            "source_namespace",
            "product_code",
            "serial_number",
        ),
        Index("ix_exceptions_error_date", "error_code", "alert_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_key: Mapped[str] = mapped_column(String(64), unique=True)
    source_namespace: Mapped[str] = mapped_column(String(255))
    unique_alert_id: Mapped[str] = mapped_column(String(100))
    alert_at: Mapped[datetime | None] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    timestamp_status: Mapped[str] = mapped_column(String(40))
    transaction_id: Mapped[str | None] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    product_code_scheme: Mapped[str | None] = mapped_column(String(100))
    product_code: Mapped[str | None] = mapped_column(String(100))
    gtin14: Mapped[str | None] = mapped_column(String(14))
    serial_number: Mapped[str | None] = mapped_column(String(100))
    provided_batch: Mapped[str | None] = mapped_column(String(100))
    stored_batch: Mapped[str | None] = mapped_column(String(100))
    organisation_id: Mapped[str | None] = mapped_column(String(100))
    source_location_id: Mapped[str | None] = mapped_column(String(100))
    last_update_location_id: Mapped[str | None] = mapped_column(String(100))
    source_market: Mapped[str | None] = mapped_column(String(100))
    business_process: Mapped[str | None] = mapped_column(String(255))
    is_intermarket: Mapped[int | None] = mapped_column(Integer)
    payload_hash: Mapped[str] = mapped_column(String(64))
    selection_time: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    last_publication_id: Mapped[int] = mapped_column(
        ForeignKey("exception_publications.id")
    )
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


class ExceptionRevision(Base):
    __tablename__ = "exception_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    revision_key: Mapped[str] = mapped_column(String(64), unique=True)
    exception_id: Mapped[int] = mapped_column(ForeignKey("nmvs_exceptions.id"))
    publication_id: Mapped[int] = mapped_column(ForeignKey("exception_publications.id"))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql")
    )
    payload_hash: Mapped[str] = mapped_column(String(64))
    source_row_id: Mapped[int | None] = evidence_row()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


PACK_AUDIT_TABLES = {"pack_audit_reports", "pack_audit_requests"}
DOMAIN_TABLES.update(PACK_AUDIT_TABLES)


class PackAuditReport(Base):
    __tablename__ = "pack_audit_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_key: Mapped[str] = mapped_column(String(64), unique=True)
    signature_key: Mapped[str] = mapped_column(String(64), index=True)
    source_namespace: Mapped[str] = mapped_column(String(255))
    code_scheme: Mapped[str] = mapped_column(String(100))
    product_code: Mapped[str] = mapped_column(String(100))
    serial_number: Mapped[str] = mapped_column(String(100))
    processing_run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"))
    acquired_artifact_id: Mapped[int] = mapped_column(
        ForeignKey("acquired_artifacts.id")
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    source_data_as_of: Mapped[str | None] = mapped_column(String(100))
    is_example: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    events_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class PackAuditRequest(Base):
    __tablename__ = "pack_audit_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    signature_key: Mapped[str] = mapped_column(String(64), unique=True)
    source_namespace: Mapped[str] = mapped_column(String(255))
    code_scheme: Mapped[str] = mapped_column(String(100))
    product_code: Mapped[str] = mapped_column(String(100))
    serial_number: Mapped[str] = mapped_column(String(100))
    requested_for_exception_id: Mapped[int | None] = mapped_column(
        ForeignKey("nmvs_exceptions.id")
    )
    request_title: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    latest_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("pack_audit_reports.id")
    )


UPLOAD_TABLES = {"upload_reports", "upload_requests"}
DOMAIN_TABLES.update(UPLOAD_TABLES)


class UploadReport(Base):
    __tablename__ = "upload_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_key: Mapped[str] = mapped_column(String(64), unique=True)
    source_namespace: Mapped[str] = mapped_column(String(255), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    acquired_artifact_id: Mapped[int] = mapped_column(
        ForeignKey("acquired_artifacts.id")
    )
    processing_run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    events_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class UploadRequest(Base):
    __tablename__ = "upload_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    source_namespace: Mapped[str] = mapped_column(String(255))
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    request_title: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer)
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    latest_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("upload_reports.id")
    )


IMPORT_CONTROL_TABLES = {
    "manual_import_requests",
    "manual_import_attempts",
    "scheduler_heartbeats",
}
DOMAIN_TABLES.update(IMPORT_CONTROL_TABLES)


class ManualImportRequest(Base):
    __tablename__ = "manual_import_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("import_schedules.id"))
    request_key: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)


class ManualImportAttempt(Base):
    __tablename__ = "manual_import_attempts"
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("import_executions.id"), primary_key=True
    )
    request_id: Mapped[int] = mapped_column(
        ForeignKey("manual_import_requests.id"), index=True
    )


class SchedulerHeartbeat(Base):
    __tablename__ = "scheduler_heartbeats"
    worker_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20))


DOMAIN_TABLES.update({"exception_reviews", "exception_review_events"})


class ExceptionReview(Base):
    __tablename__ = "exception_reviews"
    exception_id: Mapped[int] = mapped_column(
        ForeignKey("nmvs_exceptions.id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), index=True)
    cause: Mapped[str] = mapped_column(Text)
    findings: Mapped[str] = mapped_column(Text)
    next_action: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    review_reason: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    basis_payload_hash: Mapped[str] = mapped_column(String(64))
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    resolution: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    __mapper_args__: ClassVar[dict] = {"version_id_col": version}


class ExceptionReviewEvent(Base):
    __tablename__ = "exception_review_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    exception_id: Mapped[int] = mapped_column(
        ForeignKey("nmvs_exceptions.id"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    actor: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict[str, Any]] = mapped_column(JSON)
    after: Mapped[dict[str, Any]] = mapped_column(JSON)
    originating_exception_id: Mapped[int] = mapped_column(
        ForeignKey("nmvs_exceptions.id")
    )


DOMAIN_TABLES.add("intelligence_rule_revisions")


class IntelligenceRuleRevision(Base):
    __tablename__ = "intelligence_rule_revisions"
    __table_args__ = (
        Index(
            "uq_intelligence_rule_revision", "source_namespace", "version", unique=True
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_namespace: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(20))
    market: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime)


DOMAIN_TABLES.update({"crm_mahs", "crm_contacts", "end_user_import_reviews", "crm_end_users"})


class CRMMah(Base):
    __tablename__ = "crm_mahs"

    id: Mapped[int] = mapped_column(primary_key=True)
    airtable_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    gln: Mapped[str | None] = mapped_column(String(100))
    uid: Mapped[str | None] = mapped_column(String(100))
    registration_checked: Mapped[int | None] = mapped_column(Integer)
    contract_status: Mapped[str] = mapped_column(String(20))
    profile: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    parent_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_mahs.id", name="fk_crm_mahs_parent_company", ondelete="SET NULL")
    )
    source_row_id: Mapped[int | None] = evidence_row()
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__: ClassVar[dict] = {"version_id_col": version}


class CRMContact(Base):
    __tablename__ = "crm_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    airtable_id: Mapped[str] = mapped_column(String(100), unique=True)
    label: Mapped[str] = mapped_column(Text)
    function: Mapped[str | None] = mapped_column(Text)
    source_row_id: Mapped[int | None] = evidence_row()
    profile: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    __mapper_args__: ClassVar[dict] = {"version_id_col": version}

    @property
    def display_name(self):
        profile = self.profile or {}
        return " ".join(filter(None, (profile.get("first_name"), profile.get("last_name")))) or self.label


class EndUserImportReview(Base):
    __tablename__ = "end_user_import_reviews"

    staging_row_id: Mapped[int] = mapped_column(
        ForeignKey("staging_rows.id", ondelete="CASCADE"), primary_key=True
    )


class CRMEndUser(Base):
    __tablename__ = "crm_end_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    source_row_id: Mapped[int | None] = mapped_column(ForeignKey("staging_rows.id"), unique=True)
    organisation_id: Mapped[int | None] = mapped_column(
        ForeignKey("local_organisations.id"), unique=True
    )
    link_origin: Mapped[str | None] = mapped_column(String(20))
    profile: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    __mapper_args__: ClassVar[dict] = {"version_id_col": version}
