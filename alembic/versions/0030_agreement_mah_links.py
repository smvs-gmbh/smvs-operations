"""Allow agreements to link to multiple MAHs."""

import sqlalchemy as sa

from alembic import op

revision = "0030_agreement_mah_links"
down_revision = "0029_agreement_signing_date"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_agreement_mah_links",
        sa.Column(
            "agreement_id",
            sa.Integer(),
            sa.ForeignKey("crm_agreements.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "mah_id",
            sa.Integer(),
            sa.ForeignKey("crm_mahs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index(
        "ix_crm_agreement_mah_links_mah_id", "crm_agreement_mah_links", ["mah_id"]
    )
    op.execute(
        "INSERT INTO crm_agreement_mah_links (agreement_id, mah_id) SELECT id, mah_id FROM crm_agreements WHERE mah_id IS NOT NULL"
    )
    bind = op.get_bind()
    for fk in sa.inspect(bind).get_foreign_keys("crm_agreements"):
        if fk["constrained_columns"] == ["mah_id"] and fk["name"]:
            op.drop_constraint(fk["name"], "crm_agreements", type_="foreignkey")
    with op.batch_alter_table("crm_agreements") as table:
        table.drop_index("ix_crm_agreements_mah_id")
        table.drop_column("mah_id")


def downgrade():
    bind = op.get_bind()
    multiple = bind.scalar(
        sa.text(
            "SELECT COUNT(*) FROM (SELECT agreement_id FROM crm_agreement_mah_links "
            "GROUP BY agreement_id HAVING COUNT(*) > 1) AS multiple_assignments"
        )
    )
    if multiple:
        raise RuntimeError("Resolve multiple MAH assignments before downgrading.")
    with op.batch_alter_table("crm_agreements") as table:
        table.add_column(sa.Column("mah_id", sa.Integer()))
        table.create_foreign_key(
            "fk_crm_agreements_mah_id",
            "crm_mahs",
            ["mah_id"],
            ["id"],
            ondelete="SET NULL",
        )
        table.create_index("ix_crm_agreements_mah_id", ["mah_id"])
    op.execute(
        "UPDATE crm_agreements SET mah_id = (SELECT mah_id FROM crm_agreement_mah_links WHERE agreement_id = crm_agreements.id)"
    )
    op.drop_table("crm_agreement_mah_links")
