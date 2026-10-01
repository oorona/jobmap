from datetime import datetime,timedelta,timezone
import httpx
import pytest
from app.feed import Feed,FeedError,UnavailableJob
from app.fixtures import fixture_jobs
from app.contracts import Job,active,safe_url


def envelope(jobs,version='one',cursor=None,total=None):
    return {'schema_version':'1.0','snapshot_version':version,'generated_at':datetime.now(timezone.utc).isoformat(),'total':len(jobs) if total is None else total,'next_cursor':cursor,'jobs':jobs}

@pytest.mark.asyncio
async def test_upstream_credential_is_server_only_and_not_downgraded(monkeypatch):
    monkeypatch.setattr('app.feed.secret',lambda name:'mdj_test_only')
    requests=[]
    def handler(request):
        requests.append(request)
        assert request.headers['x-api-key']=='mdj_test_only'
        assert 'mdj_test_only' not in str(request.url)
        return httpx.Response(401)
    feed=Feed('live',httpx.MockTransport(handler))
    try:
        with pytest.raises(FeedError):await feed.catalog()
        assert len(requests)==1 and feed.jobs==[]
        assert 'mdj_test_only' not in str(feed.result())
    finally:await feed.client.aclose()
    fixture=Feed('fixture')
    try:assert 'x-api-key' not in fixture.client.headers
    finally:await fixture.client.aclose()

@pytest.mark.asyncio
async def test_atomic_snapshot_retry():
    jobs=fixture_jobs()[:2];count=0
    async def handler(request):
        nonlocal count
        count+=1
        if count==1:return httpx.Response(200,json=envelope(jobs[:1],cursor='next',total=2))
        if count==2:return httpx.Response(409)
        return httpx.Response(200,json=envelope(jobs,version='two'))
    feed=Feed('live',httpx.MockTransport(handler))
    result=await feed.catalog()
    assert len(result['jobs'])==2 and feed.version=='two' and count==3
    await feed.client.aclose()

@pytest.mark.asyncio
async def test_failure_keeps_valid_snapshot_but_never_uses_fixtures():
    async def fail(request):return httpx.Response(503)
    feed=Feed('live',httpx.MockTransport(fail))
    with pytest.raises(FeedError):await feed.catalog()
    assert feed.jobs==[]
    feed.jobs=[Job.model_validate(fixture_jobs()[0])];feed.loaded=__import__('time').monotonic()
    result=await feed.catalog(force=True)
    assert result['stale'] and len(result['jobs'])==1
    feed.loaded-=901
    with pytest.raises(FeedError):await feed.catalog(force=True)
    assert feed.jobs==[]
    await feed.client.aclose()

@pytest.mark.asyncio
async def test_purge_and_withdrawal():
    data=fixture_jobs()[0];job=Job.model_validate(data)
    assert not active(job,job.expires_at)
    async def gone(request):return httpx.Response(410)
    feed=Feed('live',httpx.MockTransport(gone));feed.jobs=[job]
    with pytest.raises(UnavailableJob):await feed.detail(job.id)
    assert not feed.jobs
    await feed.client.aclose()

@pytest.mark.asyncio
async def test_contract_rejects_unapproved_unsafe_duplicate_and_future():
    rows=fixture_jobs()[:1]
    rows[0]['screening']['status']='pending'
    feed=Feed('live',httpx.MockTransport(lambda r:httpx.Response(200,json=envelope(rows))))
    with pytest.raises(FeedError):await feed.catalog()
    await feed.client.aclose()
    assert not safe_url('javascript:alert(1)')
    assert not safe_url('https://user:pass@example.com')
    assert safe_url('https://example.com/jobs')
    future=Job.model_validate(fixture_jobs(datetime.now(timezone.utc)+timedelta(days=10))[0])
    assert not active(future)

@pytest.mark.asyncio
async def test_active_refresh_does_not_block_valid_snapshot():
    import asyncio
    feed=Feed('fixture');await feed.catalog()
    await feed.lock.acquire()
    try:
        result=await asyncio.wait_for(feed.catalog(force=True),.1)
        assert result['stale'] and len(result['jobs'])==48
    finally:
        feed.lock.release()
        await feed.client.aclose()
