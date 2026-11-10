"""Prevent reimport of deleted contacts without retaining contact details."""

import sqlalchemy as sa

from alembic import op

revision = "0043_contact_erasure_fingerprint"
down_revision = "0042_crm_deletion_events"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "crm_deletion_events",
        sa.Column("source_identity_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_crm_deletion_events_source_identity_hash",
        "crm_deletion_events",
        ["source_identity_hash"],
    )


def downgrade():
    op.drop_index(
        "ix_crm_deletion_events_source_identity_hash", table_name="crm_deletion_events"
    )
    op.drop_column("crm_deletion_events", "source_identity_hash")
