"""Store reviewed self-declaration invitations before delivery."""

import sqlalchemy as sa

from alembic import op

revision = "0033_declaration_drafts"
down_revision = "0032_crm_self_declarations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_declaration_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mah_id", sa.Integer(), sa.ForeignKey("crm_mahs.id"), nullable=False),
        sa.Column("data_year", sa.Integer(), nullable=False),
        sa.Column("base_fee", sa.Numeric(12, 2), nullable=False),
        sa.Column("recipient_name", sa.String(255)),
        sa.Column("recipient_email", sa.String(254)),
        sa.Column("token_nonce", sa.String(64), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("approved_by", sa.String(254)),
        sa.UniqueConstraint(
            "mah_id", "data_year", name="uq_declaration_draft_mah_year"
        ),
    )


def downgrade():
    op.drop_table("crm_declaration_drafts")
