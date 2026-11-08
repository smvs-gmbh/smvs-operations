"""Personal named CRM views, preserving previous list settings."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0039_crm_list_views"
down_revision = "0038_crm_column_order"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "crm_list_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("portal_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("directory", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "directory", "name", name="uq_crm_view_name"),
    )
    op.create_index("ix_crm_list_views_user_id", "crm_list_views", ["user_id"])
    preferences = sa.table(
        "portal_list_preferences",
        sa.column("user_id"),
        sa.column("view"),
        sa.column("defaults", sa.JSON()),
        sa.column("columns", sa.JSON()),
        sa.column("column_order", sa.JSON()),
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    connection = op.get_bind()
    for row in connection.execute(sa.select(preferences)).mappings():
        connection.execute(
            table.insert().values(
                user_id=row["user_id"],
                directory=row["view"],
                name="My view",
                config={
                    "quick_filters": row["defaults"] or {},
                    "conditions": [],
                    "columns": row["columns"],
                    "column_order": row["column_order"],
                    "sort": "",
                    "direction": "asc",
                },
                is_default=1,
                created_at=now,
                updated_at=now,
            )
        )


def downgrade():
    op.drop_table("crm_list_views")
