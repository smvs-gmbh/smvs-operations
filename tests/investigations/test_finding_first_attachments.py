import base64
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.alert_desk.test_workspace import create_workspace, fixture_database
from app.alert_desk.web import ACCESS_COOKIE
from app.alert_desk.web import create_app as gateway
from app.domain.investigations import pilot
from app.domain.investigations.pilot_api import create_app
from app.domain.models import (
    AlertDeskAccess,
    AlertDeskAttachment,
    AlertDeskEvent,
    ExceptionReview,
    NMVSException,
)


def setup(tmp_path):
    engine, factory = fixture_database(tmp_path / 'finding.db')
    create_workspace(factory)
    tokens = {'mah': 'm' * 43, 'end_user': 'e' * 43}
    with factory.begin() as s:
        for grant in s.scalars(select(AlertDeskAccess)):
            grant.session_hash = pilot.digest(tokens[grant.role])
    secret = 'finding-first-tests-' * 3
    api = create_app(factory, secret)
    return engine, factory, tokens, secret, api


def test_mah_direct_findings_optional_comment_measures_and_end_user_questions(tmp_path):
    engine, factory, tokens, secret, api = setup(tmp_path)
    headers = {'Authorization': 'Bearer ' + secret}
    try:
        with TestClient(api, client=('127.0.0.1', 1234)) as client:
            for identifier in (1, 3):
                path = f'/access/alerts/{identifier}'
                h = {**headers, 'X-Case-Session': tokens['mah']}
                case = client.get(path, headers=h).json()
                body = {'publication': identifier, 'basis': case['basis'], 'submission_key': str(uuid4()), 'finding': 'on_my_side'}
                assert client.post(path + '/findings', json=body, headers=h).status_code == 422
                body['capa'] = 'in_progress'
                assert client.post(path + '/findings', json=body, headers=h).status_code == 200
                assert client.post(path + '/findings', json=body, headers=h).status_code == 200
                saved = client.get(path, headers=h).json()['latest']
                assert saved['finding'] == 'on_my_side' and saved['capa'] == 'in_progress' and saved['comment'] == ''
                assert not client.get(path, headers=h).json()['progress']['closed']
                body.update(submission_key=str(uuid4()), finding='not_my_side', capa=None)
                assert client.post(path + '/findings', json=body, headers=h).status_code == 200
            h['X-Case-Session'] = tokens['end_user']
            body = {'publication': 3, 'basis': case['basis'], 'submission_key': str(uuid4()), 'finding': 'technical', 'capa': 'implemented'}
            assert client.post('/access/alerts/3/findings', json=body, headers=h).status_code == 422
            body['comparison'] = 'no'
            assert client.post('/access/alerts/3/findings', json=body, headers=h).status_code == 200
        public = gateway(secret, transport=httpx.ASGITransport(app=api))
        with TestClient(public, base_url='http://localhost:8014', client=('127.0.0.1', 1234)) as client:
            client.cookies.set(ACCESS_COOKIE, tokens['mah'])
            page = client.get('/alerts/3').text
            assert 'name="batch_uploaded"' not in page and 'name="serial_accepted"' not in page
            assert 'value="on_my_side"' in page and 'value="technical"' not in page
            assert 'Comment (optional)' in page and 'Attachments (optional)' in page
            client.cookies.set(ACCESS_COOKIE, tokens['end_user'])
            assert 'Does the serial number shown match the one printed on the pack?' in client.get('/alerts/3').text
            page = client.get('/alerts/1').text
            assert 'Does the submitted batch match the one printed on the pack?' in page
            assert 'value="technical"' in page and 'value="procedural"' in page
        with factory() as s:
            assert s.scalar(select(func.count()).select_from(ExceptionReview)) == 0
    finally:
        engine.dispose()


def test_attachments_independent_scoped_bounded_repeat_safe_and_staff_visible(tmp_path):
    engine, factory, tokens, secret, api = setup(tmp_path)
    origin = 'http://localhost:8014'
    public = gateway(secret, transport=httpx.ASGITransport(app=api))
    path = '/alerts/1/attachments'
    try:
        with factory() as s:
            basis = s.get(NMVSException, 1).payload_hash
        body = {'basis': basis, 'submission_key': str(uuid4()), 'filename': '../../evidence.txt', 'content': base64.b64encode(b'Synthetic evidence\n').decode()}
        with TestClient(public, base_url=origin, client=('127.0.0.1', 1234)) as client:
            client.cookies.set(ACCESS_COOKIE, tokens['mah'])
            assert client.post(path, json=body).status_code == 403
            headers = {'Origin': origin}
            result = client.post(path, json=body, headers=headers)
            assert result.status_code == 200, result.text
            file = result.json(); assert file['filename'] == 'evidence.txt'
            assert client.post(path, json=body, headers=headers).json()['id'] == file['id']
            download = client.get(path + '/' + str(file['id']))
            assert download.content == b'Synthetic evidence\n'
            assert download.headers['content-type'] == 'application/octet-stream'
            assert download.headers['content-disposition'].startswith('attachment;')
            assert download.headers['x-content-type-options'] == 'nosniff'
            assert len(client.get(path).json()['files']) == 1
            assert client.get('/alerts/3/attachments/' + str(file['id'])).status_code == 404
            client.cookies.set(ACCESS_COOKIE, tokens['end_user'])
            assert client.get(path).json()['files'] == []
            assert client.get(path + '/' + str(file['id'])).status_code == 404
            assert client.post(path, json={**body, 'submission_key': str(uuid4())}, headers=headers).status_code == 200
            client.cookies.set(ACCESS_COOKIE, tokens['mah'])
            for change in ({'basis': '0' * 64}, {'filename': 'bad.html'}, {'content': 'not-base64'}, {'filename': 'wrong.pdf'}, {'filename': 'bad\n.txt'}):
                assert client.post(path, json={**body, **change, 'submission_key': str(uuid4())}, headers=headers).status_code in (409, 422)
            assert client.post(path, json={**body, 'content': base64.b64encode(b'different').decode()}, headers=headers).status_code == 409
            # Above the old BLOB 64 KiB ceiling, through both public/private boundaries.
            large = {**body, 'filename': 'large.txt', 'submission_key': str(uuid4()), 'content': base64.b64encode(b'x' * (256 * 1024)).decode()}
            uploaded = client.post(path, json=large, headers=headers)
            assert uploaded.status_code == 200
            assert len(client.get(path + '/' + str(uploaded.json()['id'])).content) == 256 * 1024
            for _ in range(3):
                assert client.post(path, json={**body, 'submission_key': str(uuid4())}, headers=headers).status_code == 200
            assert client.post(path, json={**body, 'submission_key': str(uuid4())}, headers=headers).status_code == 422
            with factory.begin() as s:
                s.get(NMVSException, 1).payload_hash = '1' * 64
            assert client.get(path).json()['files'] == []
            assert client.get(path + '/' + str(file['id'])).status_code == 404
        # Staff retains evidence from all alert versions, without publishing it to another participant.
        workspace = create_workspace(factory)
        with TestClient(workspace, base_url='http://localhost:8021', client=('127.0.0.1',1234)) as staff:
            page = staff.get('/exceptions/1/analysis')
            assert page.status_code == 200 and 'Participant attachments' in page.text and 'Earlier alert version' in page.text
            assert staff.get(f"/exceptions/1/participant-attachments/{file['id']}").content == b'Synthetic evidence\n'
            assert staff.get(f"/exceptions/3/participant-attachments/{file['id']}").status_code == 404
        with factory() as s:
            assert s.scalar(select(func.count()).select_from(AlertDeskAttachment)) == 6
            assert s.scalar(select(func.count()).select_from(AlertDeskEvent).where(AlertDeskEvent.kind == 'Findings submitted')) == 0
    finally:
        engine.dispose()
