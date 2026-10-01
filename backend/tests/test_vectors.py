import math
import pytest
from app import vector_search as vectors, comparison
from app.fixtures import fixture_jobs


def test_vector_validation_rejects_invalid_dimensions_nan_and_zero():
    for value in ([1.0]*383, [float('nan')]*384, [0.0]*384, [float('inf')]*384):
        with pytest.raises(ValueError):
            vectors.vector_literal(value)
    assert vectors.vector_literal([1.0]*384).startswith('[1.0,')


def test_document_fingerprint_includes_full_description():
    job=fixture_jobs()[0]
    first=vectors.document_for(job,'opening text\n'+'body '*1000+'robotics')
    second=vectors.document_for(job,'opening text\n'+'body '*1000+'accounting')
    assert 'robotics' in first
    assert vectors.fingerprint(first)!=vectors.fingerprint(second)


@pytest.mark.asyncio
async def test_comparison_independent_methods_uncached_and_cosine_preserved(monkeypatch):
    jobs=fixture_jobs()[:3]
    calls=[]
    async def refine(query,prefs,corpus,sid,version,use_cache=True):
        assert corpus==jobs
        assert not use_cache
        return [{'id':jobs[0]['id'],'relevance':.9}]
    async def search(model,query,corpus):
        calls.append(model)
        assert corpus==jobs
        if model=='bge':
            raise comparison.ai.Unavailable('Index incomplete')
        return {'results':[{'id':jobs[1]['id'],'relevance':.23}], 'elapsed_ms':5,'query_ms':3,'database_ms':1,'searched_jobs':3}
    async def descriptions(ids):
        return {jobs[0]['id']:'Full description'}
    monkeypatch.setattr(comparison.ai,'refine',refine)
    monkeypatch.setattr(vectors,'search',search)
    monkeypatch.setattr(vectors,'descriptions',descriptions)
    result=await comparison.run('robotics',{},jobs,'session','version')
    assert set(calls)=={'minilm','bge','arctic'}
    assert len(result['methods'])==4
    assert result['methods'][1]['results'][0]['relevance']==.23
    assert not result['methods'][2]['available']
    assert result['methods'][3]['available']
    assert result['jobs'][0]['description_text']=='Full description'
    assert result['corpus_size']==3


@pytest.mark.asyncio
async def test_disabled_embeddings_do_not_fall_back_to_jev(monkeypatch):
    monkeypatch.setattr(vectors,'ENABLED',False)
    with pytest.raises(comparison.ai.Unavailable,match='PostgreSQL'):
        await vectors.search('minilm','robots',fixture_jobs())

@pytest.mark.asyncio
async def test_vector_and_comparison_routes_validate_sessions_versions_and_requirements(monkeypatch):
    import httpx
    from app.main import app
    from app import main
    seen=[]
    async def search(model,query,jobs,limit=30):
        seen.append((model,query,jobs))
        return {'results':[{'id':jobs[0]['id'],'relevance':.2}],'elapsed_ms':4}
    async def run(query,preferences,jobs,sid,version):
        assert all(main.ai.eligibility(j,preferences)=='match' for j in jobs)
        return {'query':query,'methods':[],'jobs':[],'catalog_version':version}
    monkeypatch.setattr(vectors,'search',search)
    monkeypatch.setattr(comparison,'run',run)
    headers={'origin':'http://localhost:3000','x-requested-with':'jev'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as client:
        catalog=(await client.get('/api/catalog')).json()
        body={'query':'robots','generation':1,'catalog_version':catalog['version'],'preferences':{'remote':True,'country':'MX','weights':{}}}
        vector=await client.post('/api/search/vector',json={**body,'model':'minilm'},headers=headers)
        assert vector.status_code==200
        assert vector.json()['threshold']==-1
        assert vector.json()['results'][0]['relevance']==.2
        assert all(main.ai.eligibility(j,body['preferences'])!='conflict' for j in seen[0][2])
        stale=await client.post('/api/search/compare',json={**body,'catalog_version':'stale'},headers=headers)
        assert stale.status_code==409
        result=await client.post('/api/search/compare',json=body,headers=headers)
        assert result.status_code==200
        assert (await client.post('/api/search/vector',json={**body,'model':'unknown'},headers=headers)).status_code==422
