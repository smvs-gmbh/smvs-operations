"""Structured local cause classification and investigation checks."""

import sqlalchemy as sa

from alembic import op

revision = "0017_structured_cause"
down_revision = "0016_exception_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("exception_reviews", sa.Column("analysis", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("exception_reviews", "analysis")
