"""Store editable signing dates on agreements."""

from datetime import date, datetime

import sqlalchemy as sa

from alembic import op

revision = "0029_agreement_signing_date"
down_revision = "0028_crm_agreements"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("crm_agreements", sa.Column("signing_date", sa.Date()))
    agreements = sa.table(
        "crm_agreements",
        sa.column("id", sa.Integer()),
        sa.column("source_row_id", sa.Integer()),
        sa.column("signing_date", sa.Date()),
    )
    staging = sa.table(
        "staging_rows",
        sa.column("id", sa.Integer()),
        sa.column("raw_row_json", sa.JSON()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(agreements.c.id, staging.c.raw_row_json).join(
            staging, staging.c.id == agreements.c.source_row_id
        )
    ).all()
    for identifier, source in rows:
        value = (source.get("Signing Date") or "").strip()
        if not value:
            continue
        signing_date = (
            datetime.strptime(value, "%d.%m.%Y").date()  # noqa: DTZ007 - calendar date only
            if "." in value
            else date.fromisoformat(value)
        )
        connection.execute(
            agreements.update()
            .where(agreements.c.id == identifier)
            .values(signing_date=signing_date)
        )


def downgrade():
    op.drop_column("crm_agreements", "signing_date")
