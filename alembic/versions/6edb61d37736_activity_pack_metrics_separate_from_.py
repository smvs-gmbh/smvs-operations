"""Preserve bulk package measurements separately from transaction counts.

Revision ID: 6edb61d37736
Revises: 0008_user_activity
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6edb61d37736"
down_revision: str | None = "0008_user_activity"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activity_facts", sa.Column("metric_kind", sa.String(40), nullable=True)
    )
    op.add_column(
        "activity_facts", sa.Column("metric_value", sa.Numeric(35, 15), nullable=True)
    )
    # The preceding schema held integer measurements only. Copy before reclassifying.
    op.execute(
        sa.text("""UPDATE activity_facts SET metric_value=transaction_count,
        metric_kind=CASE
        WHEN business_process LIKE '% - Avg. No. Packs' THEN 'mean_pack_count'
        WHEN business_process LIKE '% - Total No. Packs' THEN 'pack_count'
        ELSE 'transactions' END""")
    )
    op.execute(
        sa.text(
            "UPDATE activity_facts SET transaction_count=0 WHERE metric_kind!='transactions'"
        )
    )
    with op.batch_alter_table("activity_facts") as batch:
        batch.alter_column("metric_kind", existing_type=sa.String(40), nullable=False)
        batch.alter_column(
            "metric_value", existing_type=sa.Numeric(35, 15), nullable=False
        )


def downgrade() -> None:
    # Do not silently coerce fractional measurements into the old integer column.
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM activity_facts WHERE metric_kind!='transactions'"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError(
            "Activity metric downgrade refused: package measurement provenance would be lost."
        )
    with op.batch_alter_table("activity_facts") as batch:
        batch.drop_column("metric_value")
        batch.drop_column("metric_kind")
