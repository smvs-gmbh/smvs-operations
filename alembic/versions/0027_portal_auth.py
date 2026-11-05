"""Add internal portal users, passkeys and expiring tokens."""

import sqlalchemy as sa

from alembic import op

revision = "0027_portal_auth"
down_revision = "0026_crm_end_user_management"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("handle", sa.String(64), nullable=False, unique=True),
        sa.Column("is_admin", sa.Integer(), nullable=False),
        sa.Column("is_nmvo", sa.Integer(), nullable=False),
        sa.Column("disabled_at", sa.DateTime()),
    )
    op.create_table(
        "portal_passkeys",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("portal_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("credential_id", sa.Text(), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "portal_auth_tokens",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("portal_users.id", ondelete="CASCADE"),
        ),
        sa.Column("challenge", sa.String(64)),
        sa.Column("invitation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_portal_auth_tokens_user_id", "portal_auth_tokens", ["user_id"])
    op.create_index(
        "ix_portal_auth_tokens_expires_at", "portal_auth_tokens", ["expires_at"]
    )


def downgrade():
    op.drop_table("portal_auth_tokens")
    op.drop_table("portal_passkeys")
    op.drop_table("portal_users")
