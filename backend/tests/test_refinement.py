import asyncio
import time
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from app import intelligence as ai
from app.db import transaction,Usage,Session
from app.fixtures import fixture_jobs

@pytest.mark.asyncio
async def test_concurrent_budget_cannot_overspend():
    attempts=await asyncio.gather(*(ai.reserve(.2) for _ in range(12)),return_exceptions=True)
    assert sum(isinstance(x,str) for x in attempts)==3
    async with transaction() as db:
        assert sum(x.amount for x in (await db.scalars(select(Usage))).all())<=.75

@pytest.mark.asyncio
async def test_monthly_cap_survives_daily_reset():
    async with transaction() as db:
        today=ai.now().replace(hour=0,minute=0,second=0,microsecond=0)
        db.add(Usage(id='previous',created=today.replace(day=1).timestamp(),amount=7.49,state='reconciled'))
    with pytest.raises(ai.Unavailable):await ai.reserve(.02)

@pytest.mark.asyncio
async def test_failure_keeps_reservation_and_session_cache_isolated(monkeypatch):
    monkeypatch.setattr(ai,'REFINEMENT_ENABLED',True);monkeypatch.setattr(ai,'secret',lambda _: 'test-key')
    ai.CACHE.clear();calls=[]
    async def failed(state,questions):raise TimeoutError()
    monkeypatch.setattr(ai,'provider',failed)
    args=('python',{'remote':False,'country':'','weights':{}},fixture_jobs()[:2],'session-a','v1')
    with pytest.raises(ai.Unavailable):await ai.refine(*args)
    async with transaction() as db:
        rows=(await db.scalars(select(Usage))).all()
        assert len(rows)==1 and rows[0].amount>0 and rows[0].state=='reserved'
    async def success(state,questions):
        calls.append(state)
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=100),model_dump=lambda **_: {'answers':{k:{'noul':.9} for k in questions}})
    monkeypatch.setattr(ai,'provider',success)
    await ai.refine(*args);await ai.refine(*args)
    await ai.refine(*args[:3],'session-b','v1')
    assert len(calls)==2
    async with transaction() as db:
        rows=(await db.scalars(select(Usage))).all()
        paid=[r for r in rows if r.state=='reconciled']
        assert len(rows)==3 and len(paid)==2
        assert all(r.amount==pytest.approx(100*ai.PRICE) for r in paid)

@pytest.mark.asyncio
async def test_one_active_session_and_global_cap():
    async with transaction() as db:
        for n in range(6):db.add(Session(id=str(n),expires=time.time()+100,active_until=0))
    await ai.enter('0','peer-0')
    with pytest.raises(ai.Unavailable):await ai.enter('0','peer-0')
    for n in range(1,5):await ai.enter(str(n),'peer-'+str(n))
    with pytest.raises(ai.Unavailable):await ai.enter('5','peer-5')
    await ai.leave('0');await ai.enter('5','peer-5')


def test_hard_conflict_dominates_preferences():
    job=fixture_jobs()[5]
    assert ai.eligibility(job,{'remote':True,'weights':{'ownership':1}})=='conflict'
    unknown=fixture_jobs()[2]
    assert ai.eligibility(unknown,{'country':'MX'})=='clarify'
