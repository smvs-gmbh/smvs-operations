import runpy

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select

from app.alert_desk.test_workspace import create_workspace, fixture_database
from app.core.db.models import Base
from app.domain.investigations import pilot
from app.domain.models import AlertDeskAccess, AlertDeskAttachment, NMVSException


def test_attachment_migration_preserves_other_tables_and_refuses_evidence_loss(tmp_path):
    engine, factory = fixture_database(tmp_path / 'migration.db')
    create_workspace(factory)
    migration = runpy.run_path('alembic/versions/0058_alert_desk_attachments.py')
    try:
        with engine.begin() as c:
            Base.metadata.tables['alert_desk_attachments'].drop(c)
            migration['upgrade'].__globals__['op'] = Operations(MigrationContext.configure(c))
            migration['upgrade']()
            assert compare_metadata(MigrationContext.configure(c, opts={'include_object': lambda obj, name, kind, reflected, compare_to: kind != 'table' or name == 'alert_desk_attachments'}), Base.metadata) == []
        with factory.begin() as s:
            grant = s.scalar(select(AlertDeskAccess))
            record = s.get(NMVSException, 1)
            s.add(AlertDeskAttachment(exception_id=1, source_version=record.payload_hash, access_id=grant.id,
                contact_version=grant.contact_version, role=grant.role, crm_organisation_id=grant.crm_organisation_id,
                submission_key='synthetic', filename='evidence.txt', content_type='text/plain', byte_count=1,
                sha256='0'*64, content=b'x', created_at=pilot.now()))
        with engine.begin() as c:
            migration['downgrade'].__globals__['op'] = Operations(MigrationContext.configure(c))
            with pytest.raises(RuntimeError, match='Retain participant attachments'):
                migration['downgrade']()
            assert c.scalar(select(AlertDeskAttachment.byte_count)) == 1
    finally:
        engine.dispose()
