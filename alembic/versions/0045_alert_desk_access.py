"""Organisation-scoped Alert Desk invitations and mailbox verification."""

import sqlalchemy as sa

from alembic import op

revision = "0045_alert_desk_access"
down_revision = "0044_alert_desk_pilot"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "alert_desk_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("crm_organisation_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("contact_version", sa.Integer(), nullable=False),
        sa.Column("scope_key", sa.String(100), nullable=False),
        sa.Column(
            "invited_by", sa.Integer(), sa.ForeignKey("portal_users.id"), nullable=False
        ),
        sa.Column("invited_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime()),
        sa.Column("accepted_at", sa.DateTime()),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("invite_hash", sa.String(64), unique=True),
        sa.Column("invite_expires_at", sa.DateTime(), nullable=False),
        sa.Column("challenge_hash", sa.String(64), unique=True),
        sa.Column("code_hash", sa.String(64)),
        sa.Column("code_expires_at", sa.DateTime()),
        sa.Column("attempts_left", sa.Integer(), nullable=False),
        sa.Column("session_hash", sa.String(64), unique=True),
        sa.Column("session_expires_at", sa.DateTime()),
        sa.UniqueConstraint(
            "role",
            "crm_organisation_id",
            "contact_id",
            name="uq_alert_desk_access_scope",
        ),
    )


def downgrade():
    op.drop_table("alert_desk_access")
