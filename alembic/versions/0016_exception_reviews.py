"""Local exception review, root cause and follow-up history."""

import sqlalchemy as sa

from alembic import op

revision = "0016_exception_reviews"
down_revision = "0015_import_management"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exception_reviews",
        sa.Column(
            "exception_id",
            sa.Integer(),
            sa.ForeignKey("nmvs_exceptions.id"),
            primary_key=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cause", sa.Text(), nullable=False),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("review_reason", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("basis_payload_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_exception_reviews_status", "exception_reviews", ["status"])
    op.create_table(
        "exception_review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exception_id",
            sa.Integer(),
            sa.ForeignKey("nmvs_exceptions.id"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column(
            "originating_exception_id",
            sa.Integer(),
            sa.ForeignKey("nmvs_exceptions.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_exception_review_events_exception_id",
        "exception_review_events",
        ["exception_id"],
    )


def downgrade():
    op.drop_table("exception_review_events")
    op.drop_table("exception_reviews")
