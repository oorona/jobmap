"""Run inside the backend container: python -m evaluation.runner --track controlled."""
import argparse
import asyncio
import json
import random
import time
import uuid
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import text
from app import intelligence as ai, vector_search as vectors, comparison
from app.db import engine
from app.embedding_models import MODELS,ENCODING_VERSION
from app.feed import Feed
from .dataset import controlled,live_queries,checksum
from .bm25 import BM25

METHODS=['jev_pipeline','minilm','bge','arctic','bm25','jev_shared','minilm_jev']
PREFERENCES={'remote':False,'country':'','weights':{}}


def save(path,data):
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    staging=target.with_suffix('.partial')
    staging.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    staging.replace(target)


class Budget:
    def __init__(self,maximum):
        self.maximum=maximum;self.committed=0

    async def score(self,query,jobs,version,ids=None):
        # Every provider call retains the application's shared daily/monthly reservation gate.
        if self.committed+.00252>self.maximum:
            raise ai.Unavailable('Benchmark spending cap reached')
        telemetry={}
        try:
            rows=await ai.refine(query,PREFERENCES,jobs,'benchmark-'+version,version,use_cache=False,candidate_ids=ids,telemetry=telemetry)
            return rows,telemetry
        finally:
            self.committed+=telemetry.get('charged_usd') if telemetry.get('charged_usd') is not None else telemetry.get('reserved_usd',0)


async def controlled_run(args,data,budget):
    jobs=data['dataset']['jobs'];version=data['dataset']['hash'];lexical=BM25(jobs)
    async with engine.connect() as conn:
        if not await conn.scalar(text('SELECT pg_try_advisory_lock(721904)')):
            raise RuntimeError('Another benchmark is already running')
        try:
            # Session-local tables cannot pollute the application's current-posting index.
            await conn.execute(text('CREATE TEMP TABLE eval_vectors (id text, model text, embedding public.vector(384), PRIMARY KEY(id,model))'))
            started=time.perf_counter()
            for model in MODELS:
                for start in range(0,len(jobs),8):
                    batch=jobs[start:start+8]
                    embeddings=await vectors.encode(model,[j['search_text'] for j in batch],'document')
                    await conn.execute(text('INSERT INTO pg_temp.eval_vectors VALUES (:id,:model,CAST(:embedding AS public.vector))'),
                                       [{'id':job['id'],'model':model,'embedding':vectors.vector_literal(vector)} for job,vector in zip(batch,embeddings)])
                print(json.dumps({'event':'indexed_controlled','model':model,'jobs':len(jobs)}),flush=True)
            await conn.commit()
            data['indexing_ms']=(time.perf_counter()-started)*1000
            data['database_version']=await conn.scalar(text('SHOW server_version'))
            async def embedding(model,query,limit=72):
                started=time.perf_counter();vector=(await vectors.encode(model,[query]))[0];encoded=time.perf_counter()
                rows=(await conn.execute(text('SELECT id,1-(embedding <=> CAST(:v AS public.vector)) AS relevance FROM pg_temp.eval_vectors WHERE model=:model ORDER BY embedding <=> CAST(:v AS public.vector),id LIMIT :limit'),{'model':model,'v':vectors.vector_literal(vector),'limit':limit})).mappings().all()
                return {'results':[dict(r) for r in rows],'query_ms':(encoded-started)*1000,'database_ms':(time.perf_counter()-encoded)*1000,'api_usd':0}
            async def method(name,query):
                started=time.perf_counter();cost=0;reserved=0
                try:
                    if name in MODELS:
                        result=await embedding(name,query)
                    elif name=='bm25':
                        result={'results':lexical.search(query,len(jobs)),'api_usd':0}
                    elif name=='jev_pipeline':
                        rows,usage=await budget.score(query,jobs,version)
                        result={'results':rows,'api_usd':usage.get('charged_usd'),'reserved_usd':usage.get('reserved_usd',0)}
                    elif name=='jev_shared':
                        rows=[];known=True
                        for start in range(0,len(jobs),24):
                            batch=jobs[start:start+24]
                            part,usage=await budget.score(query,jobs,version,[j['id'] for j in batch])
                            rows.extend(part);cost+=usage.get('charged_usd') or 0;reserved+=usage.get('reserved_usd',0)
                            known=known and usage.get('charged_usd') is not None
                        result={'results':sorted(rows,key=lambda r:(-r['relevance'],r['id'])),'api_usd':cost if known else None,'reserved_usd':reserved}
                    else:
                        candidates=await embedding('minilm',query,20)
                        rows,usage=await budget.score(query,jobs,version,[r['id'] for r in candidates['results']])
                        result={'results':rows,'api_usd':usage.get('charged_usd'),'reserved_usd':usage.get('reserved_usd',0),'retrieval_ms':candidates['query_ms']+candidates['database_ms']}
                    return {'method':name,'available':True,**result,'elapsed_ms':(time.perf_counter()-started)*1000}
                except Exception as exc:
                    return {'method':name,'available':False,'results':[],'reason':str(exc) if isinstance(exc,ai.Unavailable) else type(exc).__name__,'elapsed_ms':(time.perf_counter()-started)*1000}
            rng=random.Random(args.seed)
            for repeat in range(args.repeats):
                queries=list(data['dataset']['queries']);rng.shuffle(queries)
                for query in queries:
                    order=list(METHODS);rng.shuffle(order)
                    for name in order:
                        result=await method(name,query['query'])
                        data['observations'].append({**result,'query_id':query['id'],'repeat':repeat,'category':query['category'],'split':query['split']})
                    data['committed_api_usd']=budget.committed
                    save(args.output,data)
                    print(json.dumps({'event':'query_complete','track':'controlled','query':query['id'],'repeat':repeat,'api_usd':round(budget.committed,6)}),flush=True)
                    if budget.committed+.00252>budget.maximum:
                        raise RuntimeError('Benchmark spending cap reached; partial results saved')
        finally:
            await conn.rollback()
            await conn.execute(text('SELECT pg_advisory_unlock(721904)'))


async def live_run(args,data):
    feed=Feed()
    try:
        catalog=await feed.catalog()
        if catalog['stale']:raise RuntimeError('Live feed is stale')
        jobs=[j for j in catalog['jobs'] if datetime.fromisoformat(j['source_posted_at'].replace('Z','+00:00')).timestamp()>=time.time()-45*86400]
        coverage=await vectors.status(jobs)
        if not all(m['ready'] for m in coverage['models']):raise RuntimeError('Live indexes are not fully ready')
        descriptions=await vectors.descriptions([j['id'] for j in jobs])
        dataset={'name':'job-search-live-v1','kind':'live_unlabeled','jobs':[{**j,'description_text':descriptions.get(j['id'],j['search_text'])} for j in jobs],
                 'queries':live_queries(),'qrels':{},'catalog_version':catalog['version'],'label_source':'Awaiting blind human judgments','limitations':'As-deployed pipelines have different text and candidate coverage. No accuracy claim without labels.'}
        dataset['hash']=checksum(dataset);data['dataset']=dataset
        before=await ai.usage_summary()
        # Administrator-run benchmark, serial queries, normal per-call shared spending gate.
        # It does not modify or disable the public endpoint's session/IP rate limits.
        async with engine.connect() as lock:
            if not await lock.scalar(text('SELECT pg_try_advisory_lock(721904)')):raise RuntimeError('Another benchmark is running')
            try:
                for repeat in range(args.repeats):
                    for query in dataset['queries']:
                        usage=await ai.usage_summary()
                        if usage['daily']['committed']-before['daily']['committed']+.00252>args.max_usd:
                            raise RuntimeError('Benchmark spending cap reached')
                        result=await comparison.run(query['query'],PREFERENCES,jobs,'benchmark-'+data['run_id'],catalog['version'])
                        for method in result['methods']:
                            data['observations'].append({**method,'method':method['id'],'query_id':query['id'],'repeat':repeat,'category':query['category'],'split':'unlabeled'})
                        save(args.output,data)
                        print(json.dumps({'event':'query_complete','track':'live','query':query['id'],'repeat':repeat}),flush=True)
                        await asyncio.sleep(.2)
            finally:
                await lock.execute(text('SELECT pg_advisory_unlock(721904)'))
        fresh=await feed.catalog(force=True)
        if fresh['version']!=catalog['version']:
            data['snapshot_changed']=True
            raise RuntimeError('Catalog changed during benchmark; do not compare these as a fixed-corpus run')
        after=await ai.usage_summary()
        data['shared_usage_delta_usd']=after['daily']['committed']-before['daily']['committed']
        data['cost_note']='Live cost is a shared-ledger change and may include other users; not exact benchmark attribution.'
    finally:
        await feed.client.aclose()


async def main(args):
    data={'schema_version':1,'run_id':uuid.uuid4().hex,'started_at':datetime.now(timezone.utc).isoformat(),'track':args.track,'seed':args.seed,'repeats':args.repeats,
          'models':{'jev':ai.MODEL,**{k:v['model'] for k,v in MODELS.items()}},'encoding_version':ENCODING_VERSION,
          'observations':[],'complete':False,'max_api_usd':args.max_usd,
          'methodology':{'controlled':'All 72 fictional postings use identical text of at most 1000 characters. Each embedding model searches all 72 in isolated temporary pgvector tables. Jev shared scores all 72 in batches of 24 using the same relevance question as the app. Jev pipeline retains lexical candidate selection. Hybrid uses MiniLM top 20 then Jev. BM25 k1=1.2, b=.75.',
                         'timing':'Controlled methods run sequentially in seeded randomized order. Live methods run concurrently as in the UI. Document indexing excluded, query encoding and SQL included. No application result caching. Provider-side caching is opaque.',
                         'quality':'Quality uses repeat zero only. Thresholds selected on development queries only; test queries are never used for tuning. Missing judgments are never converted to irrelevant.'}}
    if args.track=='controlled':data['dataset']=controlled()
    save(args.output,data) # Freeze query/corpus/labels before inference.
    try:
        if args.track=='controlled':await controlled_run(args,data,Budget(args.max_usd))
        else:await live_run(args,data)
        data['complete']=True
    except Exception as exc:
        data['error']=str(exc)
        raise
    finally:
        data['finished_at']=datetime.now(timezone.utc).isoformat();save(args.output,data);await engine.dispose()
    if any(not o['available'] for o in data['observations']):
        raise RuntimeError('Some methods failed; inspect saved failures before interpreting quality')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--track',choices=['controlled','live'],default='controlled')
    parser.add_argument('--output',required=True)
    parser.add_argument('--repeats',type=int,choices=[1,2,3],default=2)
    parser.add_argument('--seed',type=int,default=20261001)
    parser.add_argument('--max-usd',type=float,default=.15)
    args=parser.parse_args()
    if not 0<args.max_usd<=.5:parser.error('--max-usd must be greater than zero and at most .5')
    asyncio.run(main(args))
