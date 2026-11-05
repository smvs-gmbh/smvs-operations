"""Optional portable elapsed-time import interval.

Revision ID: 0012_import_interval
Revises: 0011_exception_precision
"""

import sqlalchemy as sa

from alembic import op

revision = "0012_import_interval"
down_revision = "0011_exception_precision"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "import_schedules", sa.Column("interval_seconds", sa.Integer(), nullable=True)
    )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM import_schedules WHERE interval_seconds IS NOT NULL"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError(
            "Import interval downgrade refused: disable/reconfigure interval schedules first."
        )
    op.drop_column("import_schedules", "interval_seconds")
