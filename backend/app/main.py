import asyncio
import httpx
import logging
import json
import re
import secrets
import time
import unicodedata
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import delete
from .config import HOST, SOURCE_MODE
from .db import Session, transaction, init_db, engine
from .feed import Feed, FeedError, UnavailableJob
from . import intelligence as ai
from . import vector_search as vectors, comparison

log=logging.getLogger('jev')
feed=Feed()


@asynccontextmanager
async def lifespan(app):
    await init_db()
    async def purge():
        while True:
            feed.purge()
            try:
                await vectors.purge()
            except Exception:
                log.warning("vector_purge_failed")
            await asyncio.sleep(30)
    task=asyncio.create_task(purge())
    index_task=asyncio.create_task(vectors.index_loop(feed))
    yield
    task.cancel()
    index_task.cancel()
    await asyncio.gather(task,index_task,return_exceptions=True)
    await feed.client.aclose()
    await engine.dispose()


app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
app.add_middleware(GZipMiddleware,minimum_size=1000)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=[HOST,'localhost','127.0.0.1','jev-backend','testserver'])


class BodyLimit:
    def __init__(self,app):
        self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method']!='POST':
            return await self.app(scope,receive,send)
        chunks=[]; size=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect':
                return
            size+=len(message.get('body',b''))
            if size>8192:
                return await JSONResponse({'detail':'Request too large'},status_code=413)(scope,receive,send)
            chunks.append(message.get('body',b''))
            if not message.get('more_body'):
                break
        sent=False
        async def limited():
            nonlocal sent
            if not sent:
                sent=True
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope,limited,send)


app.add_middleware(BodyLimit)


@app.middleware('http')
async def boundary(request:Request,call_next):
    started=time.monotonic()
    try:
        if request.url.path!='/health':
            peer=request.headers.get('x-jev-peer',request.client.host if request.client else 'unknown')
            async with transaction() as db:
                await ai.rate(db,'all:'+ai.digest(peer),120)
            if request.method=='POST':
                origins={f'https://{HOST}'}
                if HOST=='localhost':
                    origins|={'http://localhost:3000','http://127.0.0.1:3000','http://localhost:3018','http://127.0.0.1:3018'}
                if request.headers.get('origin') not in origins or request.headers.get('x-requested-with')!='jev':
                    raise HTTPException(403,'Invalid origin')
        response=await call_next(request)
    except ai.Unavailable as exc:
        response=JSONResponse({'detail':str(exc)},status_code=429,headers={'Retry-After':'60'})
    except HTTPException as exc:
        response=JSONResponse({'detail':exc.detail},status_code=exc.status_code)
    except Exception as exc:
        log.error('request_failed type=%s',type(exc).__name__)
        response=JSONResponse({'detail':'Service temporarily unavailable'},status_code=503)
    for k,v in {'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'strict-origin-when-cross-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=()','Strict-Transport-Security':'max-age=31536000; includeSubDomains','Cache-Control':'private, no-cache, must-revalidate'}.items():
        response.headers[k]=v
    log.info('request method=%s status=%s ms=%.1f',request.method,response.status_code,(time.monotonic()-started)*1000)
    return response


@app.exception_handler(FeedError)
async def feed_error(request,exc):
    return JSONResponse({'detail':'MexicoDev feed is unavailable. Try again shortly.'},status_code=503)


@app.exception_handler(UnavailableJob)
async def missing_job(request,exc):
    return JSONResponse({'detail':'This job is no longer available'},status_code=410)


@app.get('/health')
async def health():
    return {'status':'ok'}


@app.get('/api/catalog')
async def catalog(request:Request,response:Response):
    result=await feed.catalog()
    sid=request.cookies.get('jev_session','')
    async with transaction() as db:
        session=await db.get(Session,ai.digest(sid)) if sid else None
        if not session or session.expires<time.time():
            sid=secrets.token_urlsafe(32)
            db.add(Session(id=ai.digest(sid),expires=time.time()+1800,active_until=0))
            response.set_cookie('jev_session',sid,max_age=1800,secure=HOST!='localhost',httponly=True,samesite='lax')
        await db.execute(delete(Session).where(Session.expires<time.time()))
    result={**result,'refinement':await ai.availability()}
    response.headers['ETag']='W/"'+ai.digest(json.dumps(result,sort_keys=True))+'"'
    if request.headers.get('if-none-match')==response.headers['ETag']:
        response.status_code=304
        return None
    return result


@app.get('/api/status')
async def status():
    result=await feed.catalog()
    return {k:v for k,v in result.items() if k not in ('jobs','facets')} | {'live_ids':[j['id'] for j in result['jobs']],'refinement':await ai.availability()}


@app.get('/api/usage')
async def usage():
    return await ai.usage_summary()


@app.get('/api/jobs/{ident}')
async def detail(ident:str):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',ident):
        raise HTTPException(422,'Invalid job ID')
    return await feed.detail(ident)


@app.get('/api/market')
async def market(comparison:str=Query('completed',pattern='^(completed|elapsed|all)$')):
    return await feed.market(comparison)


@app.get('/api/market/jobs')
async def market_jobs(month:str=Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),skill:str=Query(min_length=1,max_length=80),second_skill:str=Query('',max_length=80),cursor:str=Query('',max_length=2000),comparison:str=Query('all',pattern='^(completed|elapsed|all)$')):
    if SOURCE_MODE=='fixture' and cursor and not re.fullmatch(r'\d{1,5}',cursor):
        raise HTTPException(422,'Invalid cursor')
    return await feed.market_jobs({'month':month,'skill':skill,'second_skill':second_skill,'cursor':cursor,'comparison':comparison,'limit':25})


@app.get('/api/search')
async def search(q:str=Query('',max_length=300),skill:str=Query('',max_length=80),work_mode:str=Query('',pattern='^(remote|hybrid|onsite|unknown)?$'),cursor:str=Query('',max_length=2000)):
    if feed.mode=='live':
        from .upstream import job_record
        from .contracts import Job, active
        data=await feed.request('search',{k:v for k,v in {'q':q,'skill':skill,'work_mode':work_mode,'cursor':cursor,'limit':25}.items() if v != ''})
        jobs=[Job.model_validate(job_record(j)) for j in data['jobs']]
        return {**data,'jobs':[j.model_dump(mode='json') for j in jobs if active(j)]}
    catalog=await feed.catalog()
    jobs=[j for j in catalog['jobs'] if q.lower() in j['search_text'].lower() and (not skill or skill in [s['id'] for s in j['skills']]) and (not work_mode or j['work_mode']['value']==work_mode)]
    return {'jobs':jobs[:25],'total':len(jobs),'next_cursor':None,'snapshot_version':catalog['version']}


class Preferences(BaseModel):
    model_config=ConfigDict(extra='forbid')
    remote:bool=False
    country:str=Field('',pattern='^([A-Z]{2})?$')
    weights:dict[str,float]=Field(default_factory=dict,max_length=6)
    @field_validator('weights')
    @classmethod
    def valid_weights(cls,value):
        for key,weight in value.items():
            if key not in {'specificity','ownership','learning','adjacent','conditions','transparency'} or not 0<=weight<=1:
                raise ValueError('Invalid preference weight')
        return value


class Refine(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query:str=Field(min_length=1,max_length=500)
    generation:int=Field(ge=0,le=2147483647)
    catalog_version:str=Field(max_length=150)
    preferences:Preferences=Field(default_factory=Preferences)


@app.post('/api/search/refine')
async def refine(body:Refine,request:Request):
    sid=ai.digest(request.cookies.get('jev_session',''))
    await ai.enter(sid,request.headers.get('x-jev-peer',request.client.host))
    result={'generation':body.generation,'catalog_version':body.catalog_version,'results':[],'available':False}
    try:
        catalog=await feed.catalog()
        if catalog['version']!=body.catalog_version:
            return {**result,'reason':'Catalog changed; refresh to refine','catalog_version':catalog['version']}
        query=''.join(c for c in unicodedata.normalize('NFKC',body.query) if unicodedata.category(c)[0]!='C')
        query=re.sub(r'(.)\1{20,}',r'\1',query).strip()
        rows=await ai.refine(query,body.preferences.model_dump(),catalog['jobs'],sid,catalog['version'])
        return {**result,'available':True,'results':rows}
    except ai.Unavailable as exc:
        return {**result,'reason':str(exc)}
    finally:
        await asyncio.shield(ai.leave(sid))


class VectorQuery(Refine):
    model: str = Field(pattern='^(minilm|bge|arctic)$')


class CompareQuery(Refine):
    days: int = Field(default=45, ge=1, le=60)


def normalize_query(value):
    query = ''.join(c for c in unicodedata.normalize('NFKC',value) if unicodedata.category(c)[0]!='C')
    query = re.sub(r'(.)\1{20,}', r'\1', query).strip()
    if not query:
        raise HTTPException(422, 'Enter a search query')
    return query


@app.get('/api/search/models')
async def search_models():
    catalog = await feed.catalog()
    return await vectors.status(catalog['jobs'])


@app.post('/api/search/vector')
async def vector_search(body:VectorQuery,request:Request):
    sid=ai.digest(request.cookies.get('jev_session',''))
    await ai.enter(sid,request.headers.get('x-jev-peer',request.client.host))
    result={'generation':body.generation,'catalog_version':body.catalog_version,'results':[],'available':False,'threshold':-1,'method':body.model}
    try:
        catalog=await feed.catalog()
        if catalog['version']!=body.catalog_version:
            return {**result,'reason':'Catalog changed; refresh to search','catalog_version':catalog['version']}
        jobs=[j for j in catalog['jobs'] if ai.eligibility(j,body.preferences.model_dump())!='conflict']
        rows=await vectors.search(body.model,normalize_query(body.query),jobs)
        return {**result,**rows,'available':True}
    except ai.Unavailable as exc:
        return {**result,'reason':str(exc)}
    except (httpx.HTTPError,ValueError):
        return {**result,'reason':'Embedding encoder unavailable'}
    finally:
        await asyncio.shield(ai.leave(sid))


@app.post('/api/search/compare')
async def compare_search(body:CompareQuery,request:Request):
    sid=ai.digest(request.cookies.get('jev_session',''))
    await ai.enter(sid,request.headers.get('x-jev-peer',request.client.host))
    try:
        catalog=await feed.catalog()
        if catalog['version']!=body.catalog_version:
            raise HTTPException(409,'Catalog changed. Refresh and run the comparison again.')
        preferences=body.preferences.model_dump()
        jobs=[j for j in catalog['jobs'] if ai.eligibility(j,preferences)=='match' and
              (body.days==60 or __import__('datetime').datetime.fromisoformat(j['source_posted_at'].replace('Z','+00:00')).timestamp()>=time.time()-body.days*86400)]
        result=await comparison.run(normalize_query(body.query),preferences,jobs,sid,catalog['version'])
        # Do not present withdrawn/expired records from a run that outlived its snapshot.
        fresh=await feed.catalog()
        if fresh['version']!=catalog['version']:
            raise HTTPException(409,'Catalog changed during comparison. Run again.')
        return {**result,'preferences':preferences,'days':body.days,'generation':body.generation}
    finally:
        await asyncio.shield(ai.leave(sid))
