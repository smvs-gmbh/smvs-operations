"""Add the CRM contacts directory."""

import sqlalchemy as sa

from alembic import op

revision = "0022_crm_contacts"
down_revision = "0021_crm_mah_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("airtable_id", sa.String(100), nullable=False, unique=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("function", sa.Text()),
        sa.Column(
            "source_row_id",
            sa.Integer(),
            sa.ForeignKey("staging_rows.id", ondelete="SET NULL"),
        ),
    )


def downgrade():
    op.drop_table("crm_contacts")
