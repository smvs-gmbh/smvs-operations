"""Store scoped A3 pilot grants and their audit events."""

import sqlalchemy as sa

from alembic import op

revision = "0044_alert_desk_pilot"
down_revision = "0043_contact_erasure_fingerprint"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "alert_desk_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exception_id",
            sa.Integer(),
            sa.ForeignKey("nmvs_exceptions.id"),
            nullable=False,
        ),
        sa.Column(
            "organisation_id",
            sa.Integer(),
            sa.ForeignKey("local_organisations.id"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("local_locations.id"),
            nullable=False,
        ),
        sa.Column("source_version", sa.String(64), nullable=False),
        sa.Column("publication", sa.JSON(), nullable=False),
        sa.Column("invite_hash", sa.String(64), unique=True),
        sa.Column("session_hash", sa.String(64), unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
    )
    op.create_index(
        "ix_alert_desk_grants_exception_id", "alert_desk_grants", ["exception_id"]
    )
    op.create_table(
        "alert_desk_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "grant_id",
            sa.Integer(),
            sa.ForeignKey("alert_desk_grants.id"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("portal_users.id")),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("submission_key", sa.String(36)),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "grant_id", "submission_key", name="uq_alert_desk_submission"
        ),
    )


def downgrade():
    op.drop_table("alert_desk_events")
    op.drop_table("alert_desk_grants")
