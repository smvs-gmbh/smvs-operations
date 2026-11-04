from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
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
