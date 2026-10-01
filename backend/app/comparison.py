"""Compare the existing Jev pipeline against three independent vector pipelines."""
import asyncio
import time
from . import intelligence as ai, vector_search as vectors
from .embedding_models import MODELS
from .retrieval import retrieve


async def run(query, preferences, jobs, session_id, version):
    async def jev():
        started = time.perf_counter()
        try:
            rows = await ai.refine(query, preferences, jobs, session_id, version, use_cache=False)
            return {'id':'jev','name':'Jev','model':ai.MODEL,'available':True,'results':rows,
                    'elapsed_ms':(time.perf_counter()-started)*1000,'searched_jobs':len(jobs),
                    'evaluated_jobs':len(retrieve(query,jobs)),'score_kind':'probability','cache_hit':False}
        except ai.Unavailable as exc:
            return {'id':'jev','name':'Jev','model':ai.MODEL,'available':False,'reason':str(exc),'results':[],
                    'elapsed_ms':(time.perf_counter()-started)*1000}
    async def embedding(key, spec):
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(vectors.search(key, query, jobs), 25)
            return {'id':key, **spec, **result, 'available':True,'score_kind':'cosine','cache_hit':False}
        except Exception as exc:
            return {'id':key, **spec, 'available':False,'results':[],
                    'elapsed_ms':(time.perf_counter()-started)*1000,
                    'reason':str(exc) if isinstance(exc,ai.Unavailable) else 'Embedding search temporarily unavailable'}
    # Run together, with individual timing and failure reporting. No model substitutes for another.
    started = time.perf_counter()
    methods = await asyncio.gather(jev(), *(embedding(key,spec) for key,spec in MODELS.items()))
    ids = {row['id'] for method in methods for row in method['results']}
    descriptions = await vectors.descriptions(list(ids))
    return {'query':query,'catalog_version':version,'corpus_size':len(jobs), 'methods':methods,
            'elapsed_ms':(time.perf_counter()-started)*1000,
            'jobs':[{**j,'description_text':descriptions.get(j['id'],j['search_text'])} for j in jobs if j['id'] in ids],
            'methodology':{'jev':'Existing lexical/alias retrieval of up to 30 candidates, then Jev judges the first 1000 characters of search_text. No result cache.',
                'embeddings':'Each model searches all eligible indexed jobs using exact PostgreSQL cosine similarity. Entire descriptions use 600-character chunks, 100-character overlap, and normalized mean pooling. No query cache.',
                'timing':'Parallel warm-model searches. Per-method server time includes query encoding and database search or Jev retrieval and API call. Initial document indexing and shared catalog loading are excluded.',
                'accuracy':'Result counts and score thresholds are not accuracy. Label jobs to measure precision among judged results; unjudged jobs are not treated as irrelevant. Recall over the full corpus is not measured.',
                'encoding_version':vectors.ENCODING_VERSION}}
