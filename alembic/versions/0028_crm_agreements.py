"""Persist MAH agreements and reversible attachment exclusions."""

import sqlalchemy as sa

from alembic import op

revision = "0028_crm_agreements"
down_revision = "0027_portal_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_agreements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.String(100), nullable=False, unique=True),
        sa.Column("contractor", sa.String(255), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "mah_id", sa.Integer(), sa.ForeignKey("crm_mahs.id", ondelete="SET NULL")
        ),
        sa.Column(
            "source_row_id",
            sa.Integer(),
            sa.ForeignKey("staging_rows.id", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_crm_agreements_mah_id", "crm_agreements", ["mah_id"])
    op.create_table(
        "crm_agreement_exclusions",
        sa.Column(
            "artifact_id",
            sa.Integer(),
            sa.ForeignKey("acquired_artifacts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade():
    op.drop_table("crm_agreement_exclusions")
    op.drop_table("crm_agreements")
