"""Add editable CRM contact profiles."""

import sqlalchemy as sa

from alembic import op

revision = "0023_crm_contact_profiles"
down_revision = "0022_crm_contacts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("crm_contacts", sa.Column("profile", sa.JSON()))
    op.add_column(
        "crm_contacts",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_column("crm_contacts", "version")
    op.drop_column("crm_contacts", "profile")
