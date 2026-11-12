"""Record published SMVS case updates and pack instructions."""

import sqlalchemy as sa

from alembic import op

revision = "0048_alert_desk_case_updates"
down_revision = "0047_alert_desk_imt_findings"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "alert_desk_case_updates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exception_id",
            sa.Integer(),
            sa.ForeignKey("nmvs_exceptions.id"),
            nullable=False,
        ),
        sa.Column("source_version", sa.String(64), nullable=False),
        sa.Column(
            "end_user_event_id", sa.Integer(), sa.ForeignKey("alert_desk_events.id")
        ),
        sa.Column(
            "actor_id", sa.Integer(), sa.ForeignKey("portal_users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("pack_instruction", sa.String(20), nullable=False),
        sa.Column("follow_up", sa.Boolean(), nullable=False),
        sa.Column("concluded", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("notification", sa.String(120), nullable=False),
    )
    op.create_index(
        "ix_alert_desk_case_updates_exception_id",
        "alert_desk_case_updates",
        ["exception_id"],
    )


def downgrade():
    op.drop_table("alert_desk_case_updates")
