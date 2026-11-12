"""Allow case findings scoped by a CRM grant without a Swiss source location."""

import sqlalchemy as sa

from alembic import op

revision = "0047_alert_desk_imt_findings"
down_revision = "0046_alert_desk_export_attribution"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("alert_desk_grants") as table:
        table.alter_column("organisation_id", existing_type=sa.Integer(), nullable=True)
        table.alter_column("location_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    with op.batch_alter_table("alert_desk_grants") as table:
        table.alter_column("location_id", existing_type=sa.Integer(), nullable=False)
        table.alter_column(
            "organisation_id", existing_type=sa.Integer(), nullable=False
        )
