"""Versioned current-posting storage, independent embedding indexing, exact pgvector search."""
import asyncio
import hashlib
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
import httpx
from sqlalchemy import text
from .db import engine, SQLITE
from .embedding_models import MODELS, ENCODING_VERSION
from . import intelligence as ai

ENABLED = os.getenv('VECTOR_SEARCH_ENABLED', 'false').lower() == 'true'
ENCODER_URL = os.getenv('EMBEDDING_URL', 'http://jev-embeddings:8010')
state = {'running': False, 'last_completed_at': None, 'error': None, 'indexed_this_run': 0}
log = logging.getLogger('jev.index')


def fingerprint(document):
    return hashlib.sha256(document.encode()).hexdigest()


def document_for(job, description):
    return f"{job['title']}\n{job['company']['name']}\n{', '.join(s['label'] for s in job['skills'])}\n{description or job['search_text']}"[:52000]


def vector_literal(vector):
    if len(vector) != 384 or any(not isinstance(x, (float, int)) or not math.isfinite(x) for x in vector) or not any(vector):
        raise ValueError('Invalid embedding dimensions or values')
    return '['+','.join(str(float(x)) for x in vector)+']'


async def encode(model, texts, kind='query'):
    async with httpx.AsyncClient(timeout=120 if kind=='document' else 20) as client:
        response = await client.post(ENCODER_URL+'/embed', json={'model':model,'texts':texts,'kind':kind})
        response.raise_for_status()
        data = response.json()
    if data['encoding_version'] != ENCODING_VERSION or len(data['vectors']) != len(texts):
        raise ValueError('Encoder version or count mismatch')
    for vector in data['vectors']:
        vector_literal(vector)
    return data['vectors']


async def purge():
    if ENABLED and not SQLITE:
        async with engine.begin() as conn:
            await conn.execute(text('DELETE FROM jev.search_jobs WHERE expires_at <= now()'))


async def synchronize(feed):
    """Never replace a healthy corpus with a failed/partial upstream snapshot."""
    catalog = await feed.catalog()
    if catalog['stale']:
        raise ai.Unavailable('Index refresh waiting for a fresh feed')
    jobs = catalog['jobs']
    ids = [j['id'] for j in jobs]
    async with engine.begin() as conn:
        await conn.execute(text('DELETE FROM jev.search_jobs WHERE NOT (id = ANY(:ids)) OR expires_at <= now()'), {'ids':ids})
        current = {r['id']:r for r in (await conn.execute(text('SELECT id, content_version, content_hash FROM jev.search_jobs'))).mappings()}
    semaphore = asyncio.Semaphore(3)
    async def update(job):
        old = current.get(job['id'])
        if old and old['content_version'] == job['content_version']:
            return
        async with semaphore:
            detail = await feed.detail(job['id'])
        if detail['content_version'] != job['content_version']:
            raise ai.Unavailable('Posting changed while indexing; retrying next refresh')
        description = detail.get('description_text') or job['search_text']
        document = document_for(job, description)
        async with engine.begin() as conn:
            await conn.execute(text('''INSERT INTO jev.search_jobs (id, content_version, content_hash, payload, description, document, expires_at)
                VALUES (:id, :version, :hash, CAST(:payload AS jsonb), :description, :document, :expires)
                ON CONFLICT(id) DO UPDATE SET content_version=EXCLUDED.content_version, content_hash=EXCLUDED.content_hash,
                payload=EXCLUDED.payload, description=EXCLUDED.description, document=EXCLUDED.document,
                expires_at=EXCLUDED.expires_at, updated_at=now()'''),
                {'id':job['id'],'version':job['content_version'],'hash':fingerprint(document),'payload':json.dumps(job),
                 'description':description,'document':document,'expires':datetime.fromisoformat(job['expires_at'].replace('Z','+00:00'))})
    # Bound both upstream concurrency and task count.
    for start in range(0, len(jobs), 12):
        await asyncio.gather(*(update(j) for j in jobs[start:start+12]))
    for model in MODELS:
        async with engine.connect() as conn:
            pending = (await conn.execute(text('''SELECT j.id, j.document, j.content_hash FROM jev.search_jobs j
                LEFT JOIN jev.job_embeddings e ON e.job_id=j.id AND e.model=:model
                WHERE j.expires_at>now() AND (e.job_id IS NULL OR e.content_hash<>j.content_hash OR e.encoding_version<>:encoding)
                ORDER BY j.id'''), {'model':model,'encoding':ENCODING_VERSION})).mappings().all()
        for start in range(0, len(pending), 8):
            batch = pending[start:start+8]
            vectors = await encode(model, [j['document'] for j in batch], 'document')
            async with engine.begin() as conn:
                for job, vector in zip(batch, vectors):
                    await conn.execute(text('''INSERT INTO jev.job_embeddings (job_id,model,content_hash,encoding_version,embedding)
                        SELECT id,:model,:hash,:encoding,CAST(:vector AS public.vector) FROM jev.search_jobs
                        WHERE id=:id AND content_hash=:hash AND expires_at>now()
                        ON CONFLICT(job_id,model) DO UPDATE SET content_hash=EXCLUDED.content_hash,
                        encoding_version=EXCLUDED.encoding_version,embedding=EXCLUDED.embedding,indexed_at=now()'''),
                        {'id':job['id'],'model':model,'hash':job['content_hash'],'encoding':ENCODING_VERSION,'vector':vector_literal(vector)})
            state['indexed_this_run'] += len(batch)
    state['last_completed_at'] = datetime.now(timezone.utc).isoformat()


async def index_loop(feed):
    if not ENABLED or SQLITE:
        return
    while True:
        state.update(running=True, error=None, indexed_this_run=0)
        try:
            await purge()
            await synchronize(feed)
        except Exception as exc:
            state['error'] = 'Index refresh incomplete; automatic retry scheduled'
            log.warning('index_refresh_failed type=%s', type(exc).__name__)
        finally:
            state['running'] = False
        await asyncio.sleep(60)


async def status(jobs):
    result = {'enabled':ENABLED and not SQLITE, 'encoding_version':ENCODING_VERSION, **state,
              'total_jobs':len(jobs), 'models':[]}
    records = []
    if result['enabled']:
        async with engine.connect() as conn:
            records = (await conn.execute(text('''SELECT j.id,j.content_version,e.model FROM jev.search_jobs j
                JOIN jev.job_embeddings e ON e.job_id=j.id AND e.content_hash=j.content_hash
                WHERE j.expires_at>now() AND e.encoding_version=:encoding'''), {'encoding':ENCODING_VERSION})).mappings().all()
    versions = {j['id']:j['content_version'] for j in jobs}
    for key, spec in MODELS.items():
        count = sum(r['model']==key and versions.get(r['id'])==r['content_version'] for r in records)
        result['models'].append({'id':key, **spec, 'indexed_jobs':count, 'ready':result['enabled'] and count==len(jobs)})
    return result


async def search(model, query, jobs, limit=30):
    if not ENABLED or SQLITE:
        raise ai.Unavailable('Embedding search requires the PostgreSQL index')
    started = time.perf_counter()
    if not jobs:
        return {'results':[], 'elapsed_ms':0, 'query_ms':0, 'database_ms':0, 'searched_jobs':0}
    ids = [j['id'] for j in jobs]
    # Reject incomplete coverage instead of making a model appear less accurate.
    async with engine.connect() as conn:
        coverage = (await conn.execute(text('''SELECT j.id,j.content_version FROM jev.search_jobs j
            JOIN jev.job_embeddings e ON e.job_id=j.id AND e.content_hash=j.content_hash
            WHERE j.id=ANY(:ids) AND j.expires_at>now() AND e.model=:model AND e.encoding_version=:encoding'''),
            {'ids':ids,'model':model,'encoding':ENCODING_VERSION})).mappings().all()
    indexed = {r['id']:r['content_version'] for r in coverage}
    if any(indexed.get(j['id'])!=j['content_version'] for j in jobs):
        raise ai.Unavailable('This model is still indexing the current jobs. Try again shortly.')
    query_started = time.perf_counter()
    vector = (await encode(model, [query]))[0]
    query_ms = (time.perf_counter()-query_started)*1000
    db_started = time.perf_counter()
    async with engine.connect() as conn:
        rows = (await conn.execute(text('''SELECT j.id, j.content_version, 1-(e.embedding <=> CAST(:vector AS public.vector)) AS relevance
            FROM jev.search_jobs j JOIN jev.job_embeddings e ON e.job_id=j.id AND e.content_hash=j.content_hash
            WHERE j.id=ANY(:ids) AND j.expires_at>now() AND e.model=:model AND e.encoding_version=:encoding
            ORDER BY e.embedding <=> CAST(:vector AS public.vector), j.id LIMIT :limit'''),
            {'ids':ids,'model':model,'encoding':ENCODING_VERSION,'vector':vector_literal(vector),'limit':limit})).mappings().all()
    versions = {j['id']:j['content_version'] for j in jobs}
    if any(versions.get(r['id']) != r['content_version'] for r in rows):
        raise ai.Unavailable('The indexed corpus changed during search. Run again.')
    return {'results':[{'id':r['id'],'relevance':max(-1,min(1,float(r['relevance']))),'evidence_ids':[]} for r in rows],
            'elapsed_ms':(time.perf_counter()-started)*1000, 'query_ms':query_ms,
            'database_ms':(time.perf_counter()-db_started)*1000, 'searched_jobs':len(jobs)}


async def descriptions(ids):
    if not ids or not ENABLED or SQLITE:
        return {}
    async with engine.connect() as conn:
        rows = (await conn.execute(text('SELECT id,description FROM jev.search_jobs WHERE id=ANY(:ids) AND expires_at>now()'), {'ids':ids})).mappings()
        return {r['id']:r['description'] for r in rows}
