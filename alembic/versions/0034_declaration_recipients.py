"""Preserve existing declaration recipients and allow multiple addresses."""

import sqlalchemy as sa

from alembic import op

revision = "0034_declaration_recipients"
down_revision = "0033_declaration_drafts"
branch_labels = None
depends_on = None

drafts = sa.table(
    "crm_declaration_drafts",
    sa.column("id", sa.Integer()),
    sa.column("recipient_email", sa.String(254)),
    sa.column("recipient_emails", sa.JSON()),
)


def upgrade():
    op.add_column("crm_declaration_drafts", sa.Column("recipient_emails", sa.JSON()))
    connection = op.get_bind()
    for identifier, email in connection.execute(
        sa.select(drafts.c.id, drafts.c.recipient_email)
    ).all():
        connection.execute(
            drafts.update()
            .where(drafts.c.id == identifier)
            .values(recipient_emails=[email] if email else [])
        )
    with op.batch_alter_table("crm_declaration_drafts") as table:
        table.alter_column("recipient_emails", existing_type=sa.JSON(), nullable=False)
        table.drop_column("recipient_email")


def downgrade():
    connection = op.get_bind()
    rows = connection.execute(sa.select(drafts.c.id, drafts.c.recipient_emails)).all()
    if any(len(emails) > 1 for _, emails in rows):
        raise RuntimeError("Resolve multiple recipients before downgrading.")
    op.add_column(
        "crm_declaration_drafts", sa.Column("recipient_email", sa.String(254))
    )
    for identifier, emails in rows:
        if emails:
            connection.execute(
                drafts.update()
                .where(drafts.c.id == identifier)
                .values(recipient_email=emails[0])
            )
    op.drop_column("crm_declaration_drafts", "recipient_emails")
