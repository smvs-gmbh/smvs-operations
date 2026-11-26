"""Retain outcomes of controlled TEST SendGrid attempts."""

import sqlalchemy as sa
from alembic import op

revision = "0056_alert_desk_mail"
down_revision = "0055_comment_templates"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "alert_desk_mail_deliveries",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("template_id", sa.String(70), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("provider_id", sa.String(200)),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM alert_desk_mail_deliveries")):
        raise RuntimeError("Retain delivery evidence before removing this schema.")
    op.drop_table("alert_desk_mail_deliveries")
