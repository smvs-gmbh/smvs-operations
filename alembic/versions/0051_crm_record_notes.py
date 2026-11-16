"""Extend internal notes to all CRM record types."""

import sqlalchemy as sa

from alembic import op

revision = "0051_crm_record_notes"
down_revision = "0050_alert_desk_responses"
branch_labels = depends_on = None

OWNERS = {
    "mah_id": "crm_mahs.id",
    "agreement_id": "crm_agreements.id",
    "self_declaration_id": "crm_self_declarations.id",
    "contact_id": "crm_contacts.id",
    "end_user_id": "crm_end_users.id",
    "it_supplier_key": None,
}
MAH_COLUMNS = "id, mah_id, author_id, text, flag, created_at, completed_at"


def create_notes_table(*, legacy):
    table = "crm_mah_notes" if legacy else "crm_record_notes"
    owners = {"mah_id": OWNERS["mah_id"]} if legacy else OWNERS
    # MySQL disallows CHECK constraints on cascading foreign key columns.
    owner_check = ()
    if not legacy and op.get_context().dialect.name not in {"mysql", "mariadb"}:
        owner_check = (
            sa.CheckConstraint(
                " + ".join(
                    f"(CASE WHEN {name} IS NULL THEN 0 ELSE 1 END)" for name in owners
                )
                + " = 1",
                name="ck_crm_record_note_owner",
            ),
        )
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), primary_key=True),
        *(
            sa.Column(
                name,
                sa.Integer(),
                sa.ForeignKey(target, ondelete="CASCADE"),
                nullable=not legacy,
            )
            if target
            else sa.Column(name, sa.String(64))
            for name, target in owners.items()
        ),
        sa.Column(
            "author_id", sa.Integer(), sa.ForeignKey("portal_users.id"), nullable=False
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("flag", sa.String(20)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.CheckConstraint(
            "flag IN ('important', 'review_later')",
            name="ck_crm_mah_note_flag" if legacy else "ck_crm_record_note_flag",
        ),
        *owner_check,
    )
    for name in owners:
        index = "ix_crm_mah_notes_mah_status" if legacy else f"ix_{table}_{name}_status"
        op.create_index(index, table, [name, "completed_at"])


def upgrade():
    create_notes_table(legacy=False)
    op.execute(
        f"INSERT INTO crm_record_notes ({MAH_COLUMNS}) SELECT {MAH_COLUMNS} FROM crm_mah_notes"
    )
    op.drop_table("crm_mah_notes")


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM crm_record_notes WHERE mah_id IS NULL LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Downgrade would discard notes on other CRM records.")
    create_notes_table(legacy=True)
    op.execute(
        f"INSERT INTO crm_mah_notes ({MAH_COLUMNS}) SELECT {MAH_COLUMNS} FROM crm_record_notes"
    )
    op.drop_table("crm_record_notes")
