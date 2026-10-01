"""Bounded candidate retrieval; Jev makes final relevance judgments."""
import re

FILLER=set('i me my we our you your a an the to of for in on at with and or that where who is are be am as it want wants would like looking look find seeking job jobs role roles work working build building develop developing please can could do doing have using use'.split())

def tokens(text):
    out=[]
    for word in re.findall(r'[a-z0-9][a-z0-9.+#-]*',text.lower()):
        word=word.rstrip('.-')
        if word in ('robot','robots','robotic','robotics'):word='robot'
        elif word=='agentic':word='agent'
        elif len(word)>4 and word.endswith('s') and not word.endswith('ss'):word=word[:-1]
        out.append(word)
    return set(out)

def retrieve(query, jobs):
    terms=tokens(query)-FILLER
    aliases={'backend':{'python','postgresql','go','rust'},'frontend':{'react','typescript','javascript'},
             'data':{'python','sql','machine-learning'},'robot':{'ros','ros2','mechatronic','embedded','autonomy'}}
    expanded={x for t in terms for x in aliases.get(t,set())}
    def rank(job):
        text=tokens(' '.join([job['search_text'],job['title'],job['company']['name'],*[s['id'] for s in job['skills']]]))
        return len(text & terms)*10+len(text & expanded)
    ranked=sorted(jobs,key=rank,reverse=True)
    plausible=[j for j in ranked if rank(j)>0]
    return (plausible or ranked)[:30]
