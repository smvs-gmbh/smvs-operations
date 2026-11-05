"""Explicit local resolution; preserve legacy review provenance."""

import sqlalchemy as sa

from alembic import op

revision = "0018_local_resolution"
down_revision = "0017_structured_cause"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "exception_reviews", sa.Column("resolution", sa.JSON(), nullable=True)
    )
    table = sa.table(
        "exception_reviews",
        sa.column("status", sa.String()),
        sa.column("resolution", sa.JSON()),
    )
    op.execute(
        table.update()
        .where(table.c.status == "reviewed")
        .values(
            status="resolved",
            resolution={
                "basis": "legacy_reviewed",
                "note": "Migrated from Reviewed; no new cause confirmation or external closure.",
            },
        )
    )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE exception_reviews SET status = 'reviewed' WHERE status = 'resolved'"
        )
    )
    op.drop_column("exception_reviews", "resolution")
