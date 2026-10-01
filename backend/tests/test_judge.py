import json
import httpx
import pytest
from evaluation.judge import cases,payload,validate,evaluate,state_for,check_resume
from evaluation.report import analyze


def fixture():
    return {'run_id':'judge-test','track':'live','seed':1,'repeats':1,'complete':True,'models':{},'encoding_version':'test','methodology':{},
            'dataset':{'hash':'snapshot','kind':'live_unlabeled','limitations':'Test.',
                       'queries':[{'id':'q','query':'Remote Python work','category':'intent'}],
                       'jobs':[{'id':'a','title':'Python developer','company':{'name':'Test'},'search_text':'Python remote','description_text':'Python remote'}]},
            'observations':[{'method':m,'repeat':0,'query_id':'q','available':True,'elapsed_ms':10,'results':[{'id':'a','relevance':.9}]} for m in ('jev','minilm','bge','arctic')]}


def judgment():
    return {'grade':2,'confidence':'high','reason':'The posting explicitly offers Python remote work.','evidence':['Python remote'],'unmet_requirements':[],'unknown_requirements':[]}


def test_blind_payload_and_schema_validation():
    case=cases(fixture())[0];request=payload(case,'judge',1024)
    user=json.loads(request['messages'][1]['content'])
    assert set(user)=={'request','posting'}
    assert not any(word in request['messages'][1]['content'] for word in ('minilm','relevance','qrels'))
    assert validate(judgment(),case)['grade']==2
    for change in ({'grade':True},{'evidence':['invented evidence']},{'unknown_requirements':['location']}):
        with pytest.raises(ValueError):validate({**judgment(),**change},case)


@pytest.mark.asyncio
async def test_judge_deduplicates_resumes_and_marks_provenance(tmp_path):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'model':'judge-version','usage':{'prompt_tokens':100,'completion_tokens':50},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(judgment())}}]})
    run=fixture()
    state=await evaluate(run,tmp_path,'judge','https://judge.example/v1','test',transport=httpx.MockTransport(handler))
    assert state['complete'] and len(calls)==1 # four search methods, one pair
    await evaluate(run,tmp_path,'judge','https://judge.example/v1','test',transport=httpx.MockTransport(handler))
    assert len(calls)==1
    summary=analyze(run,[tmp_path/'judgments.json'])
    assert summary['quality_status']=='LLM-judged pooled evidence (provisional)'
    assert summary['methods']['jev']['strong_precision_at_5']==.2
    assert 'human ground truth' in (tmp_path/'report.html').read_text()
    with pytest.raises(ValueError,match='Checkpoint'):
        check_resume(state,state_for(run,'different-model','https://judge.example/v1',1024))


@pytest.mark.asyncio
async def test_failed_or_truncated_output_is_not_a_negative_label(tmp_path):
    calls=[]
    def handler(request):
        calls.append(1)
        return httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]})
    state=await evaluate(fixture(),tmp_path,'judge','https://judge.example/v1','',transport=httpx.MockTransport(handler))
    assert not state['complete'] and not state['judgments']
    assert state['attempts'][0]['status']=='error'
    assert analyze(fixture(),[tmp_path/'judgments.json'])['methods']['jev']['ndcg_at_10'] is None
    await evaluate(fixture(),tmp_path,'judge','https://judge.example/v1','',transport=httpx.MockTransport(handler))
    assert len(calls)==1 # ambiguous/failed calls never silently billed again


def test_responses_cache_boundaries_exclude_changing_query():
    from evaluation.judge import responses_payload,response_judgment
    case=cases(fixture())[0];a=responses_payload(case,'gpt-6.1-sol',4096)
    b=responses_payload({**case,'request':'a different request'},'gpt-6.1-sol',4096)
    assert a['input'][:2]==b['input'][:2]
    assert a['input'][2]!=b['input'][2]
    assert a['prompt_cache_options']=={'mode':'explicit','ttl':'30m'}
    assert 'prompt_cache_breakpoint' not in a['input'][2]
    assert response_judgment({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(judgment())}]}]})==judgment()
    with pytest.raises(ValueError):response_judgment({'status':'incomplete','output':[]})


def test_usage_cost_counts_reasoning_once_and_cache_write_premium():
    from evaluation.judge import usage_summary
    state=state_for(fixture(),'gpt-6.1-sol','https://api.openai.com/v1',4096)
    state['attempts']=[{'usage':{'input_tokens':1000,'input_tokens_details':{'cached_tokens':700,'cache_write_tokens':200},'output_tokens':100,'output_tokens_details':{'reasoning_tokens':40}}}]
    usage=usage_summary(state)
    assert usage['total_tokens']==1100
    assert usage['uncached_input_tokens']==100
    assert usage['estimated_api_usd']==pytest.approx((100*2+700*.1+200*2.5+100*10)/1e6)


@pytest.mark.asyncio
async def test_sol_uses_responses_and_retains_cache_usage(tmp_path):
    def handler(request):
        assert request.url.path=='/v1/responses'
        assert json.loads(request.content)['prompt_cache_options']['mode']=='explicit'
        return httpx.Response(200,json={'status':'completed','model':'gpt-6.1-sol','usage':{'input_tokens':1500,'input_tokens_details':{'cached_tokens':1400,'cache_write_tokens':0},'output_tokens':100},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(judgment())}]}]})
    state=await evaluate(fixture(),tmp_path,'gpt-6.1-sol','https://judge.example/v1','test',max_tokens=4096,transport=httpx.MockTransport(handler))
    assert state['complete']
    assert json.loads((tmp_path/'usage.json').read_text())['cached_input_tokens']==1400
    page=(tmp_path/'report.html').read_text()
    assert 'Relevant jobs per request' in page and 'Judge usage and caching' in page
