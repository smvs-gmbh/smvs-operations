"""Versioned local configuration for the A7 Intelligence rule."""

import sqlalchemy as sa

from alembic import op

revision = "0019_intelligence_rules"
down_revision = "0018_local_resolution"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "intelligence_rule_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_namespace", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("market", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "uq_intelligence_rule_revision",
        "intelligence_rule_revisions",
        ["source_namespace", "version"],
        unique=True,
    )


def downgrade():
    op.drop_table("intelligence_rule_revisions")
