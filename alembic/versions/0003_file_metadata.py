"""Persist parsed file metadata per processing attempt.

Revision ID: 0003_file_metadata
Revises: 0002_artifact_content_and_failure_stage
"""
import sqlalchemy as sa

from alembic import op

revision = "0003_file_metadata"
down_revision = "0002_artifact_content_and_failure_stage"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("processing_runs", sa.Column("file_metadata", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("processing_runs", "file_metadata")
