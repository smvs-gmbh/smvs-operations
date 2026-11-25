"""Retain CSV generation receipts without retaining exported cell contents."""

import sqlalchemy as sa

from alembic import op

revision = "0052_portal_csv_exports"
down_revision = "0051_crm_record_notes"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "portal_csv_exports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("portal_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=False),
        sa.Column("table_key", sa.String(100), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("view_hash", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("byte_count", sa.BigInteger(), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("row_count >= 0", name="ck_portal_csv_export_rows"),
    )
    op.create_index("ix_portal_csv_exports_actor_created", "portal_csv_exports", ["actor_id", "created_at"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM portal_csv_exports LIMIT 1")).first():
        raise RuntimeError("Retain CSV export audit receipts before downgrading.")
    op.drop_index("ix_portal_csv_exports_actor_created", table_name="portal_csv_exports")
    op.drop_table("portal_csv_exports")
