"""Add persistent CRM End Users with optional NMVS links."""

import sqlalchemy as sa

from alembic import op

revision = "0025_crm_end_users"
down_revision = "0024_end_user_import_review"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_end_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "source_row_id",
            sa.Integer(),
            sa.ForeignKey("staging_rows.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "organisation_id",
            sa.Integer(),
            sa.ForeignKey("local_organisations.id"),
            unique=True,
        ),
        sa.Column("link_origin", sa.String(20)),
    )


def downgrade():
    op.drop_table("crm_end_users")
