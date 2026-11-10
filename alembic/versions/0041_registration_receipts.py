"""Keep registration receipts and confirmation outbox inside Operations."""

import sqlalchemy as sa

from alembic import op

revision = "0041_registration_receipts"
down_revision = "0040_end_user_registrations"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "registration_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(100), nullable=False, unique=True),
        sa.Column("submission_id", sa.String(100), nullable=False, unique=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("payload_ciphertext", sa.Text()),
        sa.Column("token_digest", sa.String(64), unique=True),
        sa.Column("token_ciphertext", sa.Text()),
        sa.Column("token_expires_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime()),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("acknowledged_revision", sa.Integer(), nullable=False),
        sa.Column("mail_status", sa.String(30), nullable=False),
        sa.Column("mail_attempts", sa.Integer(), nullable=False),
        sa.Column("mail_attempted_at", sa.DateTime()),
        sa.Column("mail_sent_at", sa.DateTime()),
        sa.Column("version", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("registration_receipts")
