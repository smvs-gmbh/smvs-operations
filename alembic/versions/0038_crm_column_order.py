"""Persist the order of visible and hidden CRM columns."""

import sqlalchemy as sa
from alembic import op

revision = "0038_crm_column_order"
down_revision = "0037_portal_list_columns"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("portal_list_preferences", sa.Column("column_order", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("portal_list_preferences", "column_order")
