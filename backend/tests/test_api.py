import httpx
import pytest
from app.main import app

@pytest.mark.asyncio
async def test_catalog_session_details_and_no_operational_routes():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as client:
        response=await client.get('/api/catalog');assert response.status_code==200
        data=response.json();assert data['source_mode']=='fixture' and len(data['jobs'])==48
        assert 'httponly' in response.headers['set-cookie'].lower()
        detail=await client.get('/api/jobs/'+data['jobs'][0]['id'])
        assert detail.status_code==200
        assert detail.json()['evidence'][0]['source_revision_id']==data['jobs'][0]['source_revision_id']
        assert (await client.get('/docs')).status_code==404
        assert (await client.get('/api/jobs/unknown')).status_code==410
        assert response.headers['x-content-type-options']=='nosniff'

@pytest.mark.asyncio
async def test_origin_body_limit_and_disabled_provider():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as client:
        catalog=(await client.get('/api/catalog')).json()
        body={'query':'python','generation':1,'catalog_version':catalog['version'],'preferences':{'remote':False,'country':'','weights':{}}}
        assert (await client.post('/api/search/refine',json=body)).status_code==403
        headers={'origin':'http://localhost:3000','x-requested-with':'jev'}
        result=await client.post('/api/search/refine',json=body,headers=headers)
        assert result.status_code==200 and not result.json()['available']
        assert (await client.post('/api/search/refine',content='x'*9000,headers=headers)).status_code==413

@pytest.mark.asyncio
async def test_market_counts_reconcile():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as client:
        data=(await client.get('/api/market?comparison=all')).json()
        for month in data['months']:
            for skill,count in month['counts'].items():
                result=(await client.get('/api/market/jobs',params={'month':month['month'],'skill':skill,'comparison':'all'})).json()
                assert result['total']==count
                assert month['percentages'][skill]==round(count/month['denominator']*100,2)

@pytest.mark.asyncio
async def test_conditional_catalog_preserves_session_and_empty_304():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as client:
        first=await client.get('/api/catalog')
        second=await client.get('/api/catalog',headers={'if-none-match':first.headers['etag']})
        assert second.status_code==304 and second.content==b''
        assert client.cookies.get('jev_session')

@pytest.mark.asyncio
async def test_public_usage_totals_separate_reservations_without_private_records():
    from datetime import datetime,timezone
    from app import intelligence as ai
    from app.db import transaction,Usage
    from unittest.mock import patch
    stamp=datetime(2026,10,15,12,tzinfo=timezone.utc)
    async with transaction() as db:
        db.add_all([Usage(id='private-call-id',created=stamp.timestamp(),amount=.01,state='reconciled'),
                    Usage(id='pending-id',created=stamp.timestamp(),amount=.02,state='reserved'),
                    Usage(id='earlier-day',created=stamp.replace(day=2).timestamp(),amount=.04,state='reconciled')])
    with patch.object(ai,'now',return_value=stamp):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as client:
            response=await client.get('/api/usage')
    data=response.json()
    assert response.status_code==200
    assert data['daily']['spent']==.01 and data['daily']['reserved']==.02
    assert data['daily']['remaining']==pytest.approx(.72)
    assert data['monthly']['spent']==pytest.approx(.05)
    assert data['monthly']['remaining']==pytest.approx(7.43)
    assert data['daily']['charged_calls']==1 and data['daily']['pending_reservations']==1
    assert data['monthly']['resets_at'].startswith('2026-11-01')
    assert 'private-call-id' not in response.text and 'pending-id' not in response.text
