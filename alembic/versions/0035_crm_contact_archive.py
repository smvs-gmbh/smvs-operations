"""Support reversible CRM contact archiving."""

import sqlalchemy as sa

from alembic import op

revision = "0035_crm_contact_archive"
down_revision = "0034_declaration_recipients"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("crm_contacts", sa.Column("archived_at", sa.DateTime()))


def downgrade():
    op.drop_column("crm_contacts", "archived_at")
