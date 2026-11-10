"""Minimal administrator deletion audit without erased personal data."""

import sqlalchemy as sa

from alembic import op

revision = "0042_crm_deletion_events"
down_revision = "0041_registration_receipts"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "crm_deletion_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("crm_deletion_events")
