"""Private, contact-scoped Alert Desk comment templates and transactional history."""

import sqlalchemy as sa

from alembic import op

revision = "0055_comment_templates"
down_revision = "0054_crm_contact_links"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "alert_desk_comment_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "contact_id", sa.Integer(), sa.ForeignKey("crm_contacts.id"), nullable=False
        ),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("crm_organisation_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("name_key", sa.String(64), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "contact_id",
            "role",
            "crm_organisation_id",
            "name_key",
            name="uq_comment_template_owner_name",
        ),
    )
    op.create_table(
        "alert_desk_comment_template_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("alert_desk_comment_templates.id"),
            nullable=False,
        ),
        sa.Column(
            "access_id",
            sa.Integer(),
            sa.ForeignKey("alert_desk_access.id"),
            nullable=False,
        ),
        sa.Column(
            "exception_id",
            sa.Integer(),
            sa.ForeignKey("nmvs_exceptions.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("alert_desk_comment_template_events")
    op.drop_table("alert_desk_comment_templates")
