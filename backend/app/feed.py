import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
import httpx
from pydantic import ValidationError
from .config import SOURCE_MODE, UPSTREAM, secret
from .contracts import Page, Job, active, safe_url
from .fixtures import fixture_jobs, market
from .upstream import job_record, market_record, comparison_param


class FeedError(Exception):
    pass


class UnavailableJob(FeedError):
    pass


class Feed:
    def __init__(self, mode=SOURCE_MODE, transport=None):
        self.mode = mode
        key = secret('mexicodev_api_key') if mode == 'live' else ''
        self.client = httpx.AsyncClient(base_url=UPSTREAM+'/', headers={'X-Api-Key':key} if key else {}, timeout=12, follow_redirects=False, transport=transport)
        self.lock = asyncio.Lock()
        self.jobs: list[Job] = []
        self.version = ''
        self.loaded = 0.0
        self.refreshed = None
        self.stale = False
        if mode not in ('live','fixture'):
            raise ValueError('SOURCE_MODE must be live or fixture')

    def purge(self):
        self.jobs = [j for j in self.jobs if active(j)]

    async def request(self, path, params=None):
        # Paths are constructed by fixed application routes, never user URLs.
        async with self.client.stream('GET', path, params=params) as response:
            if response.status_code in (404,410):
                raise UnavailableJob('Record unavailable')
            if response.status_code == 409:
                raise FeedError('snapshot_changed')
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 8_000_000:
                    raise FeedError('Upstream response too large')
            return json.loads(body)

    async def catalog(self, force=False):
        self.purge()
        if self.lock.locked() and self.loaded and time.monotonic()-self.loaded < 900:
            return {**self.result(), 'stale':True}
        async with self.lock:
            self.purge()
            if not force and self.loaded and time.monotonic()-self.loaded < 60:
                return self.result()
            try:
                deadline=time.monotonic()+25
                if self.mode == 'fixture':
                    rows = [Job.model_validate(j) for j in fixture_jobs()]
                    version = 'fixture-'+datetime.now(timezone.utc).strftime('%Y-%m-%d')
                    refreshed = datetime.now(timezone.utc).isoformat()
                else:
                    for attempt in range(3):
                        rows, seen_cursors, cursor, version = [], set(), None, None
                        try:
                            for _ in range(200):
                                remaining=deadline-time.monotonic()
                                if remaining<=0: raise FeedError('Refresh deadline exceeded')
                                data = await asyncio.wait_for(self.request('catalog', {'limit':500, **({'cursor':cursor} if cursor else {})}), remaining)
                                page = Page.model_validate({**data, 'jobs':[job_record(j) for j in data['jobs']]})
                                if version and page.snapshot_version != version:
                                    raise FeedError('snapshot_changed')
                                version = page.snapshot_version
                                rows.extend(page.jobs)
                                if len(rows)>20000:
                                    raise FeedError('Catalog limit exceeded')
                                refreshed = page.source_refreshed_at.isoformat() if page.source_refreshed_at else None
                                cursor = page.next_cursor
                                if not cursor:
                                    if len(rows)!=page.total or len({j.id for j in rows})!=len(rows):
                                        raise FeedError('Inconsistent catalog')
                                    break
                                if cursor in seen_cursors:
                                    raise FeedError('Repeated cursor')
                                seen_cursors.add(cursor)
                            else:
                                raise FeedError('Pagination limit exceeded')
                            break
                        except FeedError as exc:
                            if str(exc)!='snapshot_changed' or attempt==2:
                                raise
                # Publish only a fully validated snapshot. Failed downloads cannot erase it.
                self.jobs, self.version, self.refreshed = rows, version, refreshed
                self.loaded, self.stale = time.monotonic(), bool(data.get('stale', False)) if self.mode == 'live' else False
                self.purge()
            except (FeedError, httpx.HTTPError, ValidationError, ValueError, KeyError, TimeoutError) as exc:
                self.stale = True
                if not self.loaded or time.monotonic()-self.loaded>900:
                    self.jobs=[]
                    raise FeedError('MexicoDev feed unavailable') from exc
            return self.result()

    def result(self):
        self.purge()
        version = hashlib.sha256((self.version+','.join(j.id+':'+j.content_version for j in self.jobs)).encode()).hexdigest()[:24]
        return {'version':version,'jobs':[j.model_dump(mode='json') for j in self.jobs], 'source_mode':self.mode,
                'source_refreshed_at':self.refreshed,'stale':self.stale,'facets':sorted({s.id for j in self.jobs for s in j.skills})}

    async def detail(self, ident):
        if self.mode=='fixture':
            data=next((j for j in fixture_jobs() if j['id']==ident),None)
            if not data:
                raise UnavailableJob()
        else:
            try:
                data=await self.request('jobs/'+ident)
            except UnavailableJob:
                self.jobs=[j for j in self.jobs if j.id!=ident]
                raise
        job=Job.model_validate(job_record(data) if self.mode == 'live' else data)
        if job.id!=ident or not active(job):
            self.jobs=[j for j in self.jobs if j.id!=ident]
            raise UnavailableJob()
        # Public extra fields are explicitly selected, never passed through wholesale.
        out=job.model_dump(mode='json')
        out['description_text']=str(data.get('description_text',''))[:50000]
        passages=[{**e,'text':e.get('text',e.get('quote'))} for e in data.get('evidence',[])[:150] if isinstance(e,dict)]
        out['evidence']=[e for e in passages if isinstance(e.get('text'),str) and isinstance(e.get('id'),str) and e.get('source_revision_id')==job.source_revision_id]
        evidence_ids={e['id'] for e in out['evidence']}
        out['application_links']=[{'url':a['url'],'label':str(a.get('label','Apply'))[:200]} for a in data.get('application_links',[])[:20] if isinstance(a,dict) and safe_url(a.get('url'))]
        out['fields']={k:data.get(k) or {'status':'unknown','value':None,'evidence_ids':[]} for k in ('responsibilities','experience','education','location','time_zones','visa_sponsorship','work_authorization')}
        out['availability']='not_confirmed'
        return out

    async def market(self, comparison):
        if self.mode=='fixture':
            return market(fixture_jobs(),comparison)
        return market_record(await self.request('market',{'comparison':comparison_param(comparison)}), comparison)

    async def market_jobs(self, params):
        if self.mode=='fixture':
            rows=[j for j in fixture_jobs() if j['source_posted_at'].startswith(params['month']) and params['skill'] in [s['id'] for s in j['skills']] and (not params.get('second_skill') or params['second_skill'] in [s['id'] for s in j['skills']])]
            if params.get('comparison')=='elapsed':
                rows=[j for j in rows if datetime.fromisoformat(j['source_posted_at']).day<=datetime.now(timezone.utc).day]
            start=int(params.get('cursor') or 0)
            return {'jobs':rows[start:start+25],'total':len(rows),'next_cursor':str(start+25) if len(rows)>start+25 else None}
        params={k:v for k,v in params.items() if v != ''}
        params['comparison']=comparison_param(params.get('comparison','all'))
        data=await self.request('market/jobs',params)
        jobs=[Job.model_validate(job_record(j)) for ad in data.get('advertisements',[]) for j in ad['jobs']]
        data['jobs']=[j.model_dump(mode='json') for j in jobs if active(j)]
        data.pop('advertisements',None)
        return data
