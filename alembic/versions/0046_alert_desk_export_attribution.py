"""Record confirmed End User assignments for bounded IMT export cohorts."""

import sqlalchemy as sa

from alembic import op

revision = "0046_alert_desk_export_attribution"
down_revision = "0045_alert_desk_access"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "alert_desk_export_attributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "anchor_exception_id",
            sa.Integer(),
            sa.ForeignKey("nmvs_exceptions.id"),
            nullable=False,
        ),
        sa.Column(
            "end_user_id",
            sa.Integer(),
            sa.ForeignKey("crm_end_users.id"),
            nullable=False,
        ),
        sa.Column("source_namespace", sa.String(255), nullable=False),
        sa.Column("source_market", sa.String(100), nullable=False),
        sa.Column("source_location_id", sa.String(100), nullable=False),
        sa.Column("gtin14", sa.String(14), nullable=False),
        sa.Column("batch", sa.String(100), nullable=False),
        sa.Column("from_at", sa.DateTime(), nullable=False),
        sa.Column("until_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("anchor_exception_id", name="uq_alert_desk_export_anchor"),
    )
    op.create_index(
        "ix_alert_desk_export_attributions_end_user_id",
        "alert_desk_export_attributions",
        ["end_user_id"],
    )


def downgrade():
    op.drop_table("alert_desk_export_attributions")
