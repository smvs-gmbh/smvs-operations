"""Store personal CRM filter views."""

import sqlalchemy as sa
from alembic import op

revision = "0036_portal_list_preferences"
down_revision = "0035_crm_contact_archive"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_list_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("portal_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("view", sa.String(40), primary_key=True),
        sa.Column("visible", sa.JSON(), nullable=False),
        sa.Column("defaults", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("portal_list_preferences")
