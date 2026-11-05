"""Store reviewed End User export rows."""

import sqlalchemy as sa

from alembic import op

revision = "0024_end_user_import_review"
down_revision = "0023_crm_contact_profiles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "end_user_import_reviews",
        sa.Column(
            "staging_row_id",
            sa.Integer(),
            sa.ForeignKey("staging_rows.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade():
    op.drop_table("end_user_import_reviews")
