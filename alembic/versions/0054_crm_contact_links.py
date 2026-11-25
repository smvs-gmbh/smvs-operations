"""Durable general contact affiliations, distinct from operational role assignments."""

import sqlalchemy as sa

from alembic import op

revision = "0054_crm_contact_links"
down_revision = "0053_table_export_format"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "crm_it_supplier_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "source_row_id",
            sa.Integer(),
            sa.ForeignKey("staging_rows.id", ondelete="SET NULL"),
        ),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_table(
        "crm_contact_organisation_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "contact_id",
            sa.Integer(),
            sa.ForeignKey("crm_contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mah_id", sa.Integer(), sa.ForeignKey("crm_mahs.id", ondelete="CASCADE")
        ),
        sa.Column(
            "end_user_id",
            sa.Integer(),
            sa.ForeignKey("crm_end_users.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "supplier_id",
            sa.Integer(),
            sa.ForeignKey("crm_it_supplier_identities.id", ondelete="CASCADE"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("supplier_spoc", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column(
            "source_row_id",
            sa.Integer(),
            sa.ForeignKey("staging_rows.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(mah_id IS NOT NULL AND end_user_id IS NULL AND supplier_id IS NULL) OR (mah_id IS NULL AND end_user_id IS NOT NULL AND supplier_id IS NULL) OR (mah_id IS NULL AND end_user_id IS NULL AND supplier_id IS NOT NULL)",
            name="ck_contact_link_one_target",
        ),
        sa.UniqueConstraint("contact_id", "mah_id", name="uq_contact_link_mah"),
        sa.UniqueConstraint(
            "contact_id", "end_user_id", name="uq_contact_link_end_user"
        ),
        sa.UniqueConstraint(
            "contact_id", "supplier_id", name="uq_contact_link_supplier"
        ),
    )
    op.create_index(
        "ix_crm_contact_organisation_links_contact_id",
        "crm_contact_organisation_links",
        ["contact_id"],
    )
    op.create_table(
        "crm_contact_link_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("portal_users.id", ondelete="SET NULL"),
        ),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_crm_contact_link_events_contact_id",
        "crm_contact_link_events",
        ["contact_id"],
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM crm_contact_organisation_links LIMIT 1"))
        .first()
        or op.get_bind()
        .execute(sa.text("SELECT 1 FROM crm_contact_link_events LIMIT 1"))
        .first()
    ):
        raise RuntimeError(
            "Retain contact affiliations and their audit before downgrading."
        )
    op.drop_table("crm_contact_link_events")
    op.drop_table("crm_contact_organisation_links")
    op.drop_table("crm_it_supplier_identities")
