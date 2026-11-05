"""Maintainable CRM MAH records with optional Airtable provenance."""

import sqlalchemy as sa

from alembic import op

revision = "0020_crm_mahs"
down_revision = "0019_intelligence_rules"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_mahs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("airtable_id", sa.String(100), unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("gln", sa.String(100)),
        sa.Column("uid", sa.String(100)),
        sa.Column("registration_checked", sa.Integer()),
        sa.Column("contract_status", sa.String(20), nullable=False),
        sa.Column(
            "source_row_id",
            sa.Integer(),
            sa.ForeignKey("staging_rows.id", ondelete="SET NULL"),
        ),
        sa.Column("archived_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("crm_mahs")
