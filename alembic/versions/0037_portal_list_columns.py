"""Add personal CRM column visibility to list preferences."""

import sqlalchemy as sa
from alembic import op

revision = "0037_portal_list_columns"
down_revision = "0036_portal_list_preferences"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("portal_list_preferences", sa.Column("columns", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("portal_list_preferences", "columns")
