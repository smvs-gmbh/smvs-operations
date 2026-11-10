"""Internal registration review and attributed event history."""

import sqlalchemy as sa

from alembic import op

revision = "0040_end_user_registrations"
down_revision = "0039_crm_list_views"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "end_user_registrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intake_id", sa.String(36), nullable=False, unique=True),
        sa.Column("intake_revision", sa.Integer(), nullable=False),
        sa.Column(
            "end_user_id",
            sa.Integer(),
            sa.ForeignKey("crm_end_users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "contact_id",
            sa.Integer(),
            sa.ForeignKey("crm_contacts.id", ondelete="SET NULL"),
        ),
        sa.Column("confirmation_mail_status", sa.String(30), nullable=False),
        sa.Column("submitted_email", sa.String(254), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("security_ciphertext", sa.Text()),
        sa.Column("security_expires_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_hash", sa.String(64)),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("reviewed_by", sa.String(254)),
        sa.Column("review_note", sa.Text()),
        sa.Column("nmvs_organisation_id", sa.String(100)),
        sa.Column("nmvs_created_at", sa.DateTime()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "registration_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "registration_id",
            sa.Integer(),
            sa.ForeignKey("end_user_registrations.id"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor_user_id", sa.Integer()),
        sa.Column("actor", sa.String(254), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("note", sa.Text()),
    )
    op.create_index(
        "ix_registration_events_registration_id",
        "registration_events",
        ["registration_id"],
    )


def downgrade():
    op.drop_table("registration_events")
    op.drop_table("end_user_registrations")
