"""operational product batch and SAI mapping

Revision ID: 0005_product_batch_model
Revises: 0004_import_scheduling
Create Date: 2026-11-04 12:57:32.423909
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_product_batch_model"
down_revision: str | None = "0004_import_scheduling"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.bulk_insert(
        sa.table("import_mutexes", sa.column("import_key", sa.String(100))),
        [{"import_key": "mapping:product-batch"}],
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identity_key", sa.String(length=64), nullable=False),
        sa.Column("gtin14", sa.String(length=14), nullable=True),
        sa.Column("first_observed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gtin14"),
        sa.UniqueConstraint("identity_key"),
    )
    op.create_table(
        "mapping_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("input_key", sa.String(length=64), nullable=False),
        sa.Column("snapshot_run_id", sa.Integer(), nullable=False),
        sa.Column("sai_run_id", sa.Integer(), nullable=False),
        sa.Column("source_namespace", sa.String(length=255), nullable=False),
        sa.Column("mapping_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("statistics", sa.JSON(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["sai_run_id"],
            ["processing_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_run_id"],
            ["processing_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("input_key"),
    )
    op.create_table(
        "current_publications",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("mapping_run_id", sa.Integer(), nullable=False),
        sa.Column("source_namespace", sa.String(length=255), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("sai_exported_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mapping_run_id"],
            ["mapping_runs.id"],
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "product_source_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source_namespace", sa.String(length=255), nullable=False),
        sa.Column("code_scheme", sa.String(length=100), nullable=False),
        sa.Column("source_code", sa.String(length=100), nullable=False),
        sa.Column("reported_version", sa.Integer(), nullable=False),
        sa.Column("product_state", sa.String(length=100), nullable=True),
        sa.Column("pack_count", sa.BigInteger(), nullable=True),
        sa.Column("active_pack_count", sa.BigInteger(), nullable=True),
        sa.Column("is_observed", sa.Integer(), nullable=False),
        sa.Column("last_mapping_run_id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_mapping_run_id"],
            ["mapping_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"], ["staging_rows.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key"),
    )
    op.create_index(
        "ix_product_sources_namespace_observed",
        "product_source_records",
        ["source_namespace", "is_observed"],
        unique=False,
    )
    op.create_table(
        "sai_holders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("holder_key", sa.String(length=64), nullable=False),
        sa.Column("partner_number", sa.String(length=100), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("gln", sa.String(length=100), nullable=True),
        sa.Column("is_observed", sa.Integer(), nullable=False),
        sa.Column("last_mapping_run_id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_mapping_run_id"],
            ["mapping_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"], ["staging_rows.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("holder_key"),
    )
    op.create_table(
        "product_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_key", sa.String(length=64), nullable=False),
        sa.Column("product_source_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("detail_status", sa.String(length=40), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("last_mapping_run_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_mapping_run_id"],
            ["mapping_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_source_id"],
            ["product_source_records.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"], ["staging_rows.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_key"),
    )
    op.create_index(
        "ix_product_versions_source",
        "product_versions",
        ["product_source_id"],
        unique=False,
    )
    op.create_table(
        "sai_preparations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("preparation_key", sa.String(length=64), nullable=False),
        sa.Column("approval_number", sa.String(length=100), nullable=False),
        sa.Column("preparation_name", sa.Text(), nullable=True),
        sa.Column("holder_id", sa.Integer(), nullable=True),
        sa.Column("atc_code", sa.String(length=100), nullable=True),
        sa.Column("approval_status", sa.String(length=100), nullable=True),
        sa.Column("is_observed", sa.Integer(), nullable=False),
        sa.Column("last_mapping_run_id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["holder_id"],
            ["sai_holders.id"],
        ),
        sa.ForeignKeyConstraint(
            ["last_mapping_run_id"],
            ["mapping_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"], ["staging_rows.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("preparation_key"),
    )
    op.create_table(
        "batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_key", sa.String(length=64), nullable=False),
        sa.Column("product_source_id", sa.Integer(), nullable=False),
        sa.Column("product_version_id", sa.Integer(), nullable=False),
        sa.Column("batch_code", sa.String(length=100), nullable=False),
        sa.Column("expiry_source_text", sa.String(length=100), nullable=True),
        sa.Column("batch_state", sa.String(length=100), nullable=True),
        sa.Column("pack_count", sa.BigInteger(), nullable=True),
        sa.Column("active_pack_count", sa.BigInteger(), nullable=True),
        sa.Column("is_observed", sa.Integer(), nullable=False),
        sa.Column("last_mapping_run_id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_mapping_run_id"],
            ["mapping_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_source_id"],
            ["product_source_records.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_version_id"],
            ["product_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"], ["staging_rows.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_key"),
    )
    op.create_index(
        "ix_batches_product_observed",
        "batches",
        ["product_source_id", "is_observed"],
        unique=False,
    )
    op.create_table(
        "sai_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("package_key", sa.String(length=64), nullable=False),
        sa.Column("preparation_id", sa.Integer(), nullable=False),
        sa.Column("sequence_number", sa.String(length=100), nullable=False),
        sa.Column("package_code", sa.String(length=100), nullable=False),
        sa.Column("source_gtin", sa.String(length=100), nullable=True),
        sa.Column("gtin14", sa.String(length=14), nullable=True),
        sa.Column("description_de", sa.Text(), nullable=True),
        sa.Column("description_fr", sa.Text(), nullable=True),
        sa.Column("approval_status", sa.String(length=100), nullable=True),
        sa.Column("is_observed", sa.Integer(), nullable=False),
        sa.Column("last_mapping_run_id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_mapping_run_id"],
            ["mapping_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["preparation_id"],
            ["sai_preparations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"], ["staging_rows.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_key"),
    )
    op.create_index(
        "ix_sai_packages_gtin_observed",
        "sai_packages",
        ["gtin14", "is_observed"],
        unique=False,
    )
    op.create_table(
        "product_reference_matches",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sai_package_id", sa.Integer(), nullable=True),
        sa.Column("match_status", sa.String(length=40), nullable=False),
        sa.Column("match_reason", sa.String(length=100), nullable=False),
        sa.Column("last_mapping_run_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_mapping_run_id"],
            ["mapping_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sai_package_id"],
            ["sai_packages.id"],
        ),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_index(
        op.f("ix_product_reference_matches_match_status"),
        "product_reference_matches",
        ["match_status"],
        unique=False,
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM import_mutexes WHERE import_key = 'mapping:product-batch'")
    )
    op.drop_index(
        op.f("ix_product_reference_matches_match_status"),
        table_name="product_reference_matches",
    )
    op.drop_table("product_reference_matches")
    op.drop_index("ix_sai_packages_gtin_observed", table_name="sai_packages")
    op.drop_table("sai_packages")
    op.drop_index("ix_batches_product_observed", table_name="batches")
    op.drop_table("batches")
    op.drop_table("sai_preparations")
    op.drop_index("ix_product_versions_source", table_name="product_versions")
    op.drop_table("product_versions")
    op.drop_table("sai_holders")
    op.drop_index(
        "ix_product_sources_namespace_observed", table_name="product_source_records"
    )
    op.drop_table("product_source_records")
    op.drop_table("current_publications")
    op.drop_table("mapping_runs")
    op.drop_table("products")
