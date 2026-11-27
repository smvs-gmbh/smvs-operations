"""Participant passkeys, single-use sign-in links and scoped sessions."""

import sqlalchemy as sa

from alembic import op

revision = "0057_participant_login"
down_revision = "0056_alert_desk_mail"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "alert_desk_login_tokens",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_alert_desk_login_tokens_expires_at",
        "alert_desk_login_tokens",
        ["expires_at"],
    )
    op.create_table(
        "alert_desk_participant_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "access_id",
            sa.Integer(),
            sa.ForeignKey("alert_desk_access.id"),
            nullable=False,
        ),
        sa.Column("binding", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
    )
    op.create_index(
        "ix_alert_desk_participant_sessions_access_id",
        "alert_desk_participant_sessions",
        ["access_id"],
    )
    op.create_table(
        "alert_desk_participant_passkeys",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "access_id",
            sa.Integer(),
            sa.ForeignKey("alert_desk_access.id"),
            nullable=False,
        ),
        sa.Column("binding", sa.String(64), nullable=False),
        sa.Column("credential_id", sa.Text(), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime()),
        sa.Column("revoked_at", sa.DateTime()),
    )
    op.create_index(
        "ix_alert_desk_participant_passkeys_access_id",
        "alert_desk_participant_passkeys",
        ["access_id"],
    )
    op.create_table(
        "alert_desk_login_throttles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_alert_desk_login_throttles_expires_at",
        "alert_desk_login_throttles",
        ["expires_at"],
    )
    op.create_table(
        "alert_desk_auth_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("access_id", sa.Integer(), sa.ForeignKey("alert_desk_access.id")),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )


def downgrade():
    names = (
        "alert_desk_auth_events",
        "alert_desk_participant_passkeys",
        "alert_desk_participant_sessions",
        "alert_desk_login_tokens",
        "alert_desk_login_throttles",
    )
    if any(
        op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM " + name)) for name in names
    ):
        raise RuntimeError(
            "Retain participant authentication evidence before removing this schema."
        )
    for name in names:
        op.drop_table(name)
