"""Persist Alert Desk response settings and individual requests."""

import sqlalchemy as sa

from alembic import op

revision = "0050_alert_desk_responses"
down_revision = "0049_crm_mah_notes"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "alert_desk_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("response_days", sa.Integer(), nullable=False),
    )
    op.create_table(
        "alert_desk_response_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exception_id",
            sa.Integer(),
            sa.ForeignKey("nmvs_exceptions.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("crm_organisation_id", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.String(64), nullable=False),
        sa.Column("after_event_id", sa.Integer(), nullable=False),
        sa.Column(
            "actor_id", sa.Integer(), sa.ForeignKey("portal_users.id"), nullable=False
        ),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("reminded_on", sa.Date()),
    )
    op.create_index(
        "ix_alert_desk_response_case_role",
        "alert_desk_response_requests",
        ["exception_id", "role", "source_version"],
    )


def downgrade():
    op.drop_table("alert_desk_response_requests")
    op.drop_table("alert_desk_settings")
