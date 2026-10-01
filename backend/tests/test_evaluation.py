import math
import pytest
from evaluation.dataset import controlled
from evaluation.metrics import metrics,choose_threshold,paired_interval,quantile
from evaluation.report import analyze,load_labels,blind,pool
from evaluation.bm25 import BM25


def test_fixture_complete_independent_and_split_by_topic():
    data=controlled();assert len(data['jobs'])==72;assert len(data['queries'])==48
    assert data['hash']==controlled()['hash']
    assert all(len(j['search_text'])<=1000 for j in data['jobs'])
    dev={q['topic'] for q in data['queries'] if q['split']=='dev'}
    test={q['topic'] for q in data['queries'] if q['split']=='test'}
    assert dev.isdisjoint(test)
    for q in data['queries']:
        assert len(data['qrels'][q['id']])==72
        assert sum(g>0 for g in data['qrels'][q['id']].values())==({'keywords':6,'intent':6,'constraints':1,'exclusion':1,'no_match':0}[q['category']])
    assert any(q['category']=='no_match' and q['split']=='dev' for q in data['queries'])


def test_metrics_against_hand_computed_values():
    rows=[{'id':'b'},{'id':'a'},{'id':'c'}];grades={'a':2,'b':1,'c':0,'d':2}
    result=metrics(rows,grades,3,True)
    assert result['precision']==pytest.approx(2/3)
    assert result['recall']==pytest.approx(2/3)
    assert result['ndcg']==pytest.approx((1+3/math.log2(3))/(3+3/math.log2(3)+1/2))
    assert result['reciprocal_rank']==1
    assert metrics([{'id':'unjudged'}],grades) is None
    assert metrics(rows,grades,3,False)['recall'] is None
    assert metrics([{'id':'a'},{'id':'a'}],grades,5,True)['precision']==.2
    assert metrics([],{'a':0},5,True)['no_match_false_positive'] is False
    assert metrics([{'id':'a'}],{'a':0},5,True)['no_match_false_positive'] is True


def test_threshold_supports_unbounded_bm25_scores_and_no_matches():
    chosen=choose_threshold([{'query_id':'q','results':[{'id':'a','relevance':40}]}],{'q':{'a':0}})
    assert chosen['threshold']>40
    assert chosen['dev_macro_f1']==1


def test_paired_interval_and_quantile():
    interval=paired_interval({'a':1,'b':.8},{'a':.7,'b':.5})
    assert interval['lower_95']==pytest.approx(.3)
    assert interval['upper_95']==pytest.approx(.3)
    assert quantile([10,20,30],.95)==29


def test_bm25_exact_match_outranks_unrelated_posting():
    engine=BM25([{'id':'a','search_text':'robot robot sensors'},{'id':'b','search_text':'finance accounting taxes'}])
    assert engine.search('robot')[0]['id']=='a'


def test_unlabeled_live_reports_latency_without_fabricated_accuracy(tmp_path):
    data=controlled();data['kind']='live_unlabeled';data['qrels']={}
    run={'dataset':data,'run_id':'test-run','track':'live','seed':1,'repeats':1,'complete':True,
         'observations':[{'method':'minilm','query_id':data['queries'][0]['id'],'repeat':0,'available':True,'elapsed_ms':12,'results':[{'id':data['jobs'][0]['id'],'relevance':.8}]}]}
    result=analyze(run)
    assert result['methods']['minilm']['ndcg_at_10'] is None
    assert result['methods']['minilm']['latency_p50_ms']==12
    assert result['quality_status']=='pending human judgments'
    blind(run,tmp_path);page=(tmp_path/'blind-grade.html').read_text()
    assert '"relevance"' not in page and '"method"' not in page and '"qrels"' not in page
    assert '\\u003c' in page or '<script>' in page


def test_import_rejects_labels_for_other_snapshot(tmp_path):
    import json
    data=controlled();run={'run_id':'one','dataset':data}
    path=tmp_path/'labels.json';path.write_text(json.dumps({'run_id':'two','dataset_hash':data['hash'],'judgments':[]}))
    with pytest.raises(ValueError,match='different run'):
        load_labels(run,[path])


@pytest.mark.asyncio
async def test_explicit_candidate_scoring_does_not_run_lexical_retrieval(monkeypatch):
    from app import intelligence as ai
    from types import SimpleNamespace
    jobs=controlled()['jobs'][:2];seen=[]
    monkeypatch.setattr(ai,'REFINEMENT_ENABLED',True);monkeypatch.setattr(ai,'secret',lambda _: 'test-key')
    monkeypatch.setattr(ai,'retrieve',lambda *args: (_ for _ in ()).throw(AssertionError('retrieval must not run')))
    async def provider(state,questions):
        seen.append(state)
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=100),model_dump=lambda **_: {'answers':{k:{'noul':.8} for k in questions}})
    monkeypatch.setattr(ai,'provider',provider)
    telemetry={}
    result=await ai.refine('robots',{},jobs,'eval','version',False,candidate_ids=[jobs[1]['id']],telemetry=telemetry)
    assert [r['id'] for r in result]==[jobs[1]['id']]
    assert list(seen[0]['untrusted_references'].values())==[jobs[1]['search_text']]
    assert telemetry['charged_usd']==pytest.approx(100*ai.PRICE)
    with pytest.raises(ai.Unavailable):
        await ai.refine('robots',{},jobs,'eval','version',False,candidate_ids=['outside'])


def test_report_renders_paired_comparisons_without_overwriting_method_name(tmp_path):
    from evaluation.report import render
    data=controlled();query=data['queries'][0]
    run={'run_id':'test','track':'controlled','dataset':data,'repeats':1,'models':{},'encoding_version':'test','methodology':{}}
    summary={'quality_status':'test','limitations':'test','corpus_jobs':72,'queries':48,'quality_queries':1,'run_complete':True,'dataset_hash':data['hash'],
             'methods':{'jev_pipeline':{'name':'Jev','precision_at_5':1,'ndcg_at_10':1,'recall_at_10':1,'latency_p50_ms':10,'latency_p95_ms':20,'successes':1,'attempts':1}},
             'per_query':{'jev_pipeline':{}},'paired_comparisons':[{'method':'jev_pipeline','reference':'bge',**paired_interval({'a':1,'b':1},{'a':.5,'b':.5})}]}
    render(run,summary,tmp_path)
    assert 'Jev deployed pipeline minus BGE' in (tmp_path/'report.html').read_text()
