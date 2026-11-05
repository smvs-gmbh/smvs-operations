"""Enable manual End Users, profile edits and reversible archiving."""

import sqlalchemy as sa

from alembic import op

revision = "0026_crm_end_user_management"
down_revision = "0025_crm_end_users"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("crm_end_users") as table:
        table.alter_column("source_row_id", existing_type=sa.Integer(), nullable=True)
        table.add_column(sa.Column("profile", sa.JSON()))
        table.add_column(sa.Column("archived_at", sa.DateTime()))
        table.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )


def downgrade():
    with op.batch_alter_table("crm_end_users") as table:
        table.drop_column("version")
        table.drop_column("archived_at")
        table.drop_column("profile")
        table.alter_column("source_row_id", existing_type=sa.Integer(), nullable=False)
