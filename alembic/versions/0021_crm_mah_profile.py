"""Add an editable MAH profile and parent company relationship."""

import sqlalchemy as sa

from alembic import op

revision = "0021_crm_mah_profile"
down_revision = "0020_crm_mahs"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("crm_mahs") as table:
        table.add_column(sa.Column("profile", sa.JSON()))
        table.add_column(sa.Column("parent_company_id", sa.Integer()))
        table.create_foreign_key(
            "fk_crm_mahs_parent_company",
            "crm_mahs",
            ["parent_company_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("crm_mahs") as table:
        table.drop_constraint("fk_crm_mahs_parent_company", type_="foreignkey")
        table.drop_column("parent_company_id")
        table.drop_column("profile")
