"""Retain source-bound participant attachments independently of findings."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMBLOB

from alembic import op

revision = '0058_alert_desk_attachments'
down_revision = '0057_participant_login'
branch_labels = depends_on = None


def upgrade():
    op.create_table('alert_desk_attachments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('exception_id', sa.Integer(), sa.ForeignKey('nmvs_exceptions.id'), nullable=False),
        sa.Column('source_version', sa.String(64), nullable=False),
        sa.Column('access_id', sa.Integer(), sa.ForeignKey('alert_desk_access.id'), nullable=False),
        sa.Column('contact_version', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('crm_organisation_id', sa.Integer(), nullable=False),
        sa.Column('submission_key', sa.String(36), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(40), nullable=False),
        sa.Column('byte_count', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('content', sa.LargeBinary().with_variant(MEDIUMBLOB(), 'mysql'), nullable=False),
        sa.UniqueConstraint('access_id', 'submission_key', name='uq_alert_desk_attachment_submission'))
    op.create_index('ix_alert_desk_attachments_exception_id', 'alert_desk_attachments', ['exception_id'])


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM alert_desk_attachments')):
        raise RuntimeError('Retain participant attachments before downgrading.')
    op.drop_table('alert_desk_attachments')
