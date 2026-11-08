"""Record MAH transfers and their notes."""

import sqlalchemy as sa

from alembic import op

revision = "0031_crm_mah_transfers"
down_revision = "0030_agreement_mah_links"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_mah_transfers",
        sa.Column(
            "source_mah_id",
            sa.Integer(),
            sa.ForeignKey("crm_mahs.id"),
            primary_key=True,
        ),
        sa.Column(
            "target_mah_id", sa.Integer(), sa.ForeignKey("crm_mahs.id"), nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_crm_mah_transfers_target_mah_id", "crm_mah_transfers", ["target_mah_id"]
    )


def downgrade():
    op.drop_table("crm_mah_transfers")
