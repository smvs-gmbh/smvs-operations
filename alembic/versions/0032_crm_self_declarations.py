"""Store imported MAH self-declarations with their source evidence."""

import sqlalchemy as sa

from alembic import op

revision = "0032_crm_self_declarations"
down_revision = "0031_crm_mah_transfers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_self_declarations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "source_row_id",
            sa.Integer(),
            sa.ForeignKey("staging_rows.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "mah_id", sa.Integer(), sa.ForeignKey("crm_mahs.id", ondelete="SET NULL")
        ),
        sa.Column("record_label", sa.String(255), nullable=False),
        sa.Column("source_mah_name", sa.String(255), nullable=False),
        sa.Column("declaration_year", sa.Integer(), nullable=False),
        sa.Column("packs_sold", sa.BigInteger()),
        sa.Column("status", sa.String(80)),
    )
    op.create_index(
        "ix_crm_self_declarations_mah_id", "crm_self_declarations", ["mah_id"]
    )


def downgrade():
    op.drop_table("crm_self_declarations")
