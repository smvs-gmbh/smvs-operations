"""Add internal notes to MAH records."""

import sqlalchemy as sa

from alembic import op

revision = "0049_crm_mah_notes"
down_revision = "0048_alert_desk_case_updates"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "crm_mah_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "mah_id",
            sa.Integer(),
            sa.ForeignKey("crm_mahs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id", sa.Integer(), sa.ForeignKey("portal_users.id"), nullable=False
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("flag", sa.String(20)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.CheckConstraint(
            "flag IN ('important', 'review_later')", name="ck_crm_mah_note_flag"
        ),
    )
    op.create_index(
        "ix_crm_mah_notes_mah_status", "crm_mah_notes", ["mah_id", "completed_at"]
    )


def downgrade():
    op.drop_table("crm_mah_notes")
