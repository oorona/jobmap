import httpx
import pytest
from app.feed import Feed
from app.upstream import job_record, market_record
from app.fixtures import fixture_jobs
from app.contracts import Job


def test_producer_rubric_titles_and_worldwide():
    data=fixture_jobs()[0]
    data.update(title=None,role_kind='multiple_roles',eligible_countries={'status':'unknown'},
                worldwide={'status':'stated','value':True,'evidence_ids':['e1']},
                dimensions={'learning_support':{'score':2.7,'rubric_version':'jobs-v1','evidence_ids':['e1']}})
    result=Job.model_validate(job_record(data))
    assert result.title=='Multiple roles'
    assert result.dimensions['learning'].score==pytest.approx(.9)
    assert result.eligible_countries.value==['worldwide']
    assert data['dimensions']['learning_support']['score']==2.7
    data['dimensions']['learning_support']['score']=None
    assert job_record(data)['dimensions']['learning']['score'] is None
    data['dimensions']['learning_support']['score']=4
    with pytest.raises(ValueError):job_record(data)


def test_market_windows_counts_and_coverage():
    data={'months':[{'month':'2026-09','included':True,'coverage':{'complete':True},'skills':[{'id':'python','count':3,'percent':60}]},
                    {'month':'2026-08','included':False,'coverage':None,'skills':[]}], 'note':'Retained only'}
    result=market_record(data,'completed')
    assert len(result['months'])==1
    assert result['months'][0]['counts']['python']==3
    assert result['months'][0]['percentages']['python']==60
    assert result['months'][0]['complete']
    assert len(market_record(data,'all')['months'])==2


@pytest.mark.asyncio
async def test_detail_quotes_and_advertisement_drilldown():
    data=fixture_jobs()[0]
    data['evidence']=[{'id':'e1','quote':'Source passage','source_revision_id':data['source_revision_id']}]
    def handler(request):
        if request.url.path.endswith('/market/jobs'):
            assert request.url.params['comparison']=='month_to_date'
            assert 'second_skill' not in request.url.params and 'cursor' not in request.url.params
            return httpx.Response(200,json={'advertisements':[{'jobs':[data]}],'total':1,'next_cursor':None})
        return httpx.Response(200,json=data)
    feed=Feed('live',httpx.MockTransport(handler))
    try:
        detail=await feed.detail(data['id'])
        assert detail['evidence'][0]['text']=='Source passage'
        records=await feed.market_jobs({'month':'2026-09','skill':'python','second_skill':'','cursor':'','comparison':'elapsed'})
        assert records['jobs'][0]['id']==data['id'] and records['total']==1
    finally:await feed.client.aclose()
