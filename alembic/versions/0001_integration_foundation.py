"""Create integration and source-faithful staging foundation.

Revision ID: 0001_integration_foundation
Revises:
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "0001_integration_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("channel_name", sa.String(100), nullable=False),
        sa.Column("report_type", sa.String(100), nullable=False),
        sa.Column("requested_snapshot_date", sa.Date(), nullable=True),
        sa.Column("days_in_past", sa.Integer(), nullable=True),
        sa.Column("from_date", sa.DateTime(), nullable=True),
        sa.Column("to_date", sa.DateTime(), nullable=True),
        sa.Column("requested_api_version", sa.String(50), nullable=True),
        sa.Column("used_api_version", sa.String(50), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "acquired_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("integration_job_id", sa.Integer(), sa.ForeignKey("integration_jobs.id"), nullable=False),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("channel_name", sa.String(100), nullable=False),
        sa.Column("report_type", sa.String(100), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("content_length", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("report_metadata", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("processing_status", sa.String(40), nullable=False),
        sa.Column("artifact_bytes", mysql.LONGBLOB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("sha256", name="uq_acquired_artifacts_sha256"),
    )
    op.create_index("ix_acquired_artifacts_job", "acquired_artifacts", ["integration_job_id"])
    op.create_table(
        "processing_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("artifact_id", sa.Integer(), sa.ForeignKey("acquired_artifacts.id"), nullable=False),
        sa.Column("run_type", sa.String(40), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False),
        sa.Column("transform_version", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("failure_stage", sa.String(60), nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_processing_runs_artifact", "processing_runs", ["artifact_id"])
    op.create_table(
        "staging_datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("processing_run_id", sa.Integer(), sa.ForeignKey("processing_runs.id"), nullable=False),
        sa.Column("artifact_id", sa.Integer(), sa.ForeignKey("acquired_artifacts.id"), nullable=False),
        sa.Column("source_dataset_name", sa.String(255), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False),
        sa.Column("source_headers", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("extraction_status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("processing_run_id", "source_dataset_name", name="uq_staging_dataset_run_name"),
    )
    op.create_index("ix_staging_datasets_artifact", "staging_datasets", ["artifact_id"])
    op.create_table(
        "staging_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("staging_dataset_id", sa.Integer(), sa.ForeignKey("staging_datasets.id"), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("source_record_hash", sa.String(64), nullable=False),
        sa.Column("raw_row_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("staging_dataset_id", "source_row_number", name="uq_staging_row_source_order"),
    )
    op.create_index("ix_staging_rows_dataset_hash", "staging_rows", ["staging_dataset_id", "source_record_hash"])


def downgrade() -> None:
    op.drop_index("ix_staging_rows_dataset_hash", table_name="staging_rows")
    op.drop_table("staging_rows")
    op.drop_index("ix_staging_datasets_artifact", table_name="staging_datasets")
    op.drop_table("staging_datasets")
    op.drop_index("ix_processing_runs_artifact", table_name="processing_runs")
    op.drop_table("processing_runs")
    op.drop_index("ix_acquired_artifacts_job", table_name="acquired_artifacts")
    op.drop_table("acquired_artifacts")
    op.drop_table("integration_jobs")
