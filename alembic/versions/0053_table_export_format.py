"""Distinguish CSV and typed Excel generation receipts; retain old CSV receipts."""

import sqlalchemy as sa

from alembic import op

revision = "0053_table_export_format"
down_revision = "0052_portal_csv_exports"
branch_labels = depends_on = None


def upgrade():
    op.add_column("portal_csv_exports", sa.Column("file_format", sa.String(8), nullable=False, server_default="csv"))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM portal_csv_exports WHERE file_format != 'csv' LIMIT 1")).first():
        raise RuntimeError("Retain Excel export format provenance before downgrading.")
    op.drop_column("portal_csv_exports", "file_format")
