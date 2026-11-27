from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.alert_desk.test_workspace import create_workspace, fixture_database
from app.domain.investigations import pilot
from app.domain.investigations.pilot_api import create_app
from app.domain.models import AlertDeskAccess, AlertDeskResponseRequest, NMVSException
from tests.investigations.mah_support import request_mah_review


def test_mah_policy_is_enforced_for_all_views_search_detail_templates_and_writes(tmp_path):
    engine, factory = fixture_database(tmp_path / 'mah.db')
    create_workspace(factory)
    secret = 'mah-visibility-test-' * 3
    token = 'm' * 43
    ids = {}
    with factory.begin() as s:
        grant = s.scalar(select(AlertDeskAccess).where(AlertDeskAccess.role == 'mah'))
        grant.session_hash = pilot.digest(token)
        source = s.get(NMVSException, 3)
        columns = {c.key: getattr(source,c.key) for c in NMVSException.__table__.columns if c.key!='id'}
        for code in ('A52','A68','UNKNOWN'):
            row=NMVSException(**{**columns,'alert_key':pilot.digest(code),'unique_alert_id':'POLICY-'+code,'error_code':code})
            s.add(row);s.flush();ids[code]=row.id
        other=NMVSException(**{**columns,'alert_key':pilot.digest('other-product'),'unique_alert_id':'OTHER-PRODUCT','error_code':'A24','gtin14':'09999999999999'})
        s.add(other);s.flush();other_id=other.id
    headers={'Authorization':'Bearer '+secret,'X-Case-Session':token}
    try:
        with TestClient(create_app(factory,secret),client=('127.0.0.1',1234)) as client:
            def visible(**params):
                return {r['id'] for r in client.get('/access/alerts',headers=headers,params=params).json()['rows']}
            assert visible()=={1,2,3,ids['A52']}
            for view in ('my_cases','all','completed','on_hold'):
                assert not visible(view=view)&{4,5,6,7,ids['A68'],ids['UNKNOWN']}
                assert visible(view=view,q='A7')==set()
            for identifier in (4,5,6,7,ids['A68'],ids['UNKNOWN'],other_id):
                path=f'/access/alerts/{identifier}'
                assert client.get(path,headers=headers).status_code==404
                assert client.get(path+'/comment-templates',headers=headers).status_code==404
                assert client.post(path+'/comment-templates',headers=headers,json={'command':'create','name':'Hidden','text':'Not permitted'}).status_code==404
                body={'publication':identifier,'basis':columns['payload_hash'],'submission_key':str(uuid4()),'finding':'investigating','own_cause':True}
                assert client.post(path+'/findings',headers=headers,json=body).status_code==404
            # Staff requests must be possible before participant visibility exists.
            request_mah_review(factory,[4,6,ids['A68'],other_id])
            assert visible()=={1,2,3,4,6,ids['A52'],ids['A68']}
            assert client.get(f'/access/alerts/{other_id}',headers=headers).status_code==404
            assert client.get('/access/alerts/4',headers=headers).json()['batch_count']==0
            request_mah_review(factory,[5])
            assert client.get('/access/alerts/4',headers=headers).json()['batch_count']==2
            with factory.begin() as s:
                req=s.scalar(select(AlertDeskResponseRequest).where(AlertDeskResponseRequest.exception_id==6))
                req.crm_organisation_id+=100
            assert 6 not in visible()
            with factory.begin() as s:
                req=s.scalar(select(AlertDeskResponseRequest).where(AlertDeskResponseRequest.exception_id==6))
                req.crm_organisation_id-=100;req.source_version='0'*64
            assert 6 not in visible()
            # A declared own cause is evidence only after an authorised submission.
            with factory.begin() as s:
                req=s.scalar(select(AlertDeskResponseRequest).where(AlertDeskResponseRequest.exception_id==6))
                req.source_version=s.get(NMVSException,6).payload_hash
            record=client.get('/access/alerts/6',headers=headers).json()
            body={'publication':6,'basis':record['basis'],'submission_key':str(uuid4()),'finding':'investigating','own_cause':True}
            assert client.post('/access/alerts/6/findings',headers=headers,json=body).status_code==200
            with factory.begin() as s:
                req=s.scalar(select(AlertDeskResponseRequest).where(AlertDeskResponseRequest.exception_id==6));req.source_version='0'*64
            assert 6 in visible()
            with factory.begin() as s:s.get(NMVSException,6).payload_hash='1'*64
            assert 6 not in visible()
    finally:engine.dispose()
