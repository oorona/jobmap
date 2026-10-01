from app.retrieval import retrieve
from app.fixtures import fixture_jobs

def test_natural_language_retrieves_domain_ahead_of_common_words():
    template=fixture_jobs()[0]
    generic=[{**template,'id':str(i),'title':'Web engineer','search_text':'I want to build a platform with you','skills':[]} for i in range(40)]
    robot={**template,'id':'robot','title':'Robotics engineer','search_text':'Autonomous robotics systems','skills':[]}
    rows=retrieve('I want to build robots',generic+[robot])
    assert [j['id'] for j in rows]==['robot']

def test_unknown_intent_still_gets_bounded_semantic_candidates():
    jobs=fixture_jobs()
    assert len(retrieve('meaningful work',jobs))==30

def test_agent_keyword_retrieves_explicit_and_agentic_titles():
    template=fixture_jobs()[0]
    jobs=[{**template,'id':str(i),'title':title,'search_text':title,'skills':[]} for i,title in enumerate(['Web engineer','Agent Builder','Agentic AI engineer'])]
    assert {j['title'] for j in retrieve('agent',jobs)}=={'Agent Builder','Agentic AI engineer'}
