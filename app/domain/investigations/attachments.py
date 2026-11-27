"""Retained participant evidence, scoped independently of findings and comments."""

import base64
import binascii
import hashlib
from pathlib import PurePosixPath

from fastapi import HTTPException
from sqlalchemy import select

from app.alert_desk.attachment_schema import MAX_BYTES, MAX_FILES, Upload
from app.domain.investigations import pilot, rca
from app.domain.models import (
    AlertDeskAttachment,
    AlertDeskGrant,
    ExceptionReview,
)

TYPES = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg',
         '.jpeg': 'image/jpeg', '.txt': 'text/plain', '.log': 'text/plain', '.csv': 'text/csv'}




def metadata(row):
    return {'id': row.id, 'filename': row.filename, 'bytes': row.byte_count,
            'role': row.role, 'at': row.created_at.isoformat() + 'Z',
            'source_version': row.source_version}


def scope(record, grant):
    return select(AlertDeskAttachment).where(
        AlertDeskAttachment.exception_id == record.id,
        AlertDeskAttachment.role == grant.role,
        AlertDeskAttachment.crm_organisation_id == grant.crm_organisation_id,
        AlertDeskAttachment.source_version == record.payload_hash,
    )


def validate_file(body):
    filename = PurePosixPath(body.filename.replace('\\', '/')).name
    if not filename or any(ord(c) < 32 or ord(c) == 127 for c in filename):
        raise HTTPException(422, 'Use a valid filename.')
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in TYPES:
        raise HTTPException(422, 'Use PDF, PNG, JPEG, TXT, LOG or CSV files.')
    try:
        content = base64.b64decode(body.content, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, 'Invalid file content.') from None
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(422, 'Select a non-empty file of at most 5 MiB.')
    valid = (suffix == '.pdf' and content.startswith(b'%PDF-')) or (
        suffix == '.png' and content.startswith(b'\x89PNG\r\n\x1a\n')) or (
        suffix in {'.jpg', '.jpeg'} and content.startswith(b'\xff\xd8\xff'))
    if suffix in {'.txt', '.log', '.csv'}:
        try:
            content.decode('utf-8-sig')
            valid = b'\x00' not in content
        except UnicodeDecodeError:
            valid = False
    if not valid:
        raise HTTPException(422, 'The file content does not match its supported file type.')
    return filename, TYPES[suffix], content


def install(app, sessions, capability, active, current_case, existing_grant):
    from typing import Annotated

    from fastapi import Depends

    @app.get('/access/alerts/{identifier}/attachments')
    def listing(identifier: int, token: Annotated[str, Depends(capability)]):
        with sessions() as session:
            grant, crm = active(session, token)
            record = current_case(session, grant, crm, identifier)
            return {'files': [metadata(r) for r in session.scalars(scope(record, grant).order_by(AlertDeskAttachment.id))]}

    @app.get('/access/alerts/{identifier}/attachments/{attachment_id}')
    def download(identifier: int, attachment_id: int, token: Annotated[str, Depends(capability)]):
        with sessions() as session:
            grant, crm = active(session, token)
            record = current_case(session, grant, crm, identifier)
            row = session.scalar(scope(record, grant).where(AlertDeskAttachment.id == attachment_id))
            if not row:
                raise HTTPException(404, 'Attachment unavailable.')
            if hashlib.sha256(row.content).hexdigest() != row.sha256 or len(row.content) != row.byte_count:
                raise HTTPException(503, 'Attachment integrity check failed.')
            return {**metadata(row), 'content': base64.b64encode(row.content).decode('ascii')}

    @app.post('/access/alerts/{identifier}/attachments')
    def upload(identifier: int, body: Upload, token: Annotated[str, Depends(capability)]):
        with sessions() as session, session.begin():
            grant, crm = active(session, token, lock=True)
            record = current_case(session, grant, crm, identifier, lock=True)
            if body.basis != record.payload_hash:
                raise HTTPException(409, 'Reload the case before uploading.')
            filename, content_type, content = validate_file(body)
            digest = hashlib.sha256(content).hexdigest()
            previous = session.scalar(select(AlertDeskAttachment).where(
                AlertDeskAttachment.access_id == grant.id,
                AlertDeskAttachment.submission_key == str(body.submission_key)))
            if previous:
                if (previous.exception_id, previous.source_version, previous.filename, previous.sha256) != (record.id, body.basis, filename, digest):
                    raise HTTPException(409, 'This upload reference was already used.')
                return metadata(previous)
            if rca.is_closed(session.get(ExceptionReview, record.id), record):
                raise HTTPException(409, 'This case is closed.')
            if len(session.scalars(scope(record, grant)).all()) >= MAX_FILES:
                raise HTTPException(422, 'At most five files per organisation and role may be attached to this alert version.')
            row = AlertDeskAttachment(exception_id=record.id, source_version=body.basis,
                access_id=grant.id, contact_version=grant.contact_version,
                role=grant.role, crm_organisation_id=crm.id,
                filename=filename, content_type=content_type, byte_count=len(content),
                sha256=digest, content=content, created_at=pilot.now(),
                submission_key=str(body.submission_key))
            session.add(row); session.flush()
            case_grant = existing_grant(session, grant, record)
            if not case_grant:
                case_grant = AlertDeskGrant(exception_id=record.id, source_version=record.payload_hash,
                    publication={'organisation_access': grant.id, 'audience': grant.role,
                                 'recipient': {'contact': grant.contact_id}}, expires_at=pilot.now())
                session.add(case_grant); session.flush()
            pilot.append_event(session, case_grant, 'Attachment uploaded', data={
                'attachment': row.id, 'filename': filename, 'sha256': digest, 'bytes': len(content)})
            return metadata(row)

    return listing, download, upload
