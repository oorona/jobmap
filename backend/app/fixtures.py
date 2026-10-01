"""Invented contract fixtures, never silently substituted for the live API."""
from datetime import datetime, timedelta, timezone
from collections import Counter

ARCHETYPES = [
 ('Northstar Labs','Platform engineer',['python','postgresql','kubernetes'],'remote','Build the deployment platform used by our engineering teams. You own design decisions and reliability.', 'ownership'),
 ('Fieldwork','Frontend engineer',['typescript','react'],'remote','Build accessible tools for field scientists. Pair with senior engineers through weekly mentorship.', 'learning'),
 ('Juniper Systems','Backend engineer',['rust','postgresql'],'hybrid','Design reliable event processing. Salary: $140,000 to $180,000 USD per year.', 'transparency'),
 ('Tidal Research','ML engineer',['python','machine-learning'],'remote','Develop models for coastal forecasting. We welcome equivalent experience from adjacent disciplines.', 'adjacent'),
 ('Common Ground','Full stack developer',['typescript','react','postgresql'],'remote','Build community scheduling tools. Flexible hours and 30 days paid leave.', 'conditions'),
 ('Orbit Tools','Developer experience engineer',['go','kubernetes'],'onsite','Own our build systems and improve developer workflows in our Austin office.', 'ownership'),
 ('Moss Studio','Product engineer',['typescript','react'],'remote','Ship tools for independent creators. You will design, build, and maintain our editor.', 'specificity'),
 ('Signal Foundry','Data engineer',['python','sql','aws'],'remote','Build warehouse pipelines with clear data contracts. Learning budget and regular mentoring.', 'learning'),
 ('Cedar Health','Multiple roles',['python','typescript','react'],'hybrid','Hiring software and data engineers. Shared healthcare platform team; individual requirements vary.', 'specificity'),
 ('Copper Cloud','Infrastructure engineer',['go','aws','kubernetes'],'remote','Operate a distributed storage service. Four-day week and flexible hours.', 'conditions'),
 ('Lantern Maps','Mobile engineer',['swift','typescript'],'onsite','Create offline mapping applications with our team in Mexico City. Salary: $90,000 USD per year.', 'transparency'),
 ('Paperplane','Backend developer',['python','postgresql'],'remote','Build document collaboration APIs. Equivalent experience and career transitions are welcome.', 'adjacent'),
]
DIM_LABELS = {'ownership':'Stated ownership','learning':'Learning support','transparency':'Compensation disclosed','adjacent':'Adjacent experience welcome','conditions':'Stated working conditions','specificity':'Specific responsibilities'}


def fixture_jobs(at=None):
    at = at or datetime.now(timezone.utc)
    anchor = at.replace(hour=0, minute=0, second=0, microsecond=0)
    jobs = []
    for n in range(48):
        company,title,skills,mode,description,dimension = ARCHETYPES[n % len(ARCHETYPES)]
        posted = anchor - timedelta(days=n+1)
        ident = f'demo_{n+1:03}'
        revision = f'rev_{ident}'
        quote = f'{company} | {title} | {mode}. {description}'
        countries = ['MX','US'] if n%3==0 else ['DE'] if n%3==1 else None
        quote += ' Eligible countries: ' + ', '.join(countries) + '.' if countries else ' Country eligibility is not stated.'
        ev = f'{revision}_p0'
        jobs.append({'id':ident,'advertisement_id':f'ad_{ident}','opportunity_id':f'opp_{ident}',
            'company':{'id':f'company_{n%12}', 'name':company},'title':title,'role_kind':'multiple_roles' if title=='Multiple roles' else 'single_role',
            'source_posted_at':posted.isoformat(),'expires_at':(posted+timedelta(days=60)).isoformat(),'updated_at':posted.isoformat(),
            'source_revision_id':revision,'content_version':revision,'skills':[{'id':s,'label':s.replace('-',' ').title()} for s in skills],
            'work_mode':{'status':'stated','value':mode,'evidence_ids':[ev]},
            'eligible_countries':{'status':'stated' if countries else 'unknown','value':countries,'evidence_ids':[ev] if countries else []},
            'compensation':{'status':'stated' if dimension=='transparency' else 'unknown','value':{'original':description} if dimension=='transparency' else None,'evidence_ids':[ev] if dimension=='transparency' else []},
            'search_text':quote+' '+' '.join(skills), 'dimensions':{dimension:{'score':.94,'label':DIM_LABELS[dimension],'evidence_ids':[ev]}},
            'unknowns':['visa_sponsorship','work_authorization']+(['eligible_countries'] if not countries else []),
            'screening':{'status':'passed','rubric_version':'fixture-only'},'canonical_url':f'https://example.com/jobs/{ident}',
            'source_url':f'https://example.com/source/{ident}', 'description_text':quote,
            'evidence':[{'id':ev,'source_revision_id':revision,'text':quote,'start':0,'end':len(quote)}],
            'application_links':[{'url':f'https://example.com/apply/{ident}','label':'Example application (not a real job)','evidence_ids':[ev]}],
            'responsibilities':{'status':'stated','value':description,'evidence_ids':[ev]}, 'experience':{'status':'unknown','value':None,'evidence_ids':[]},
            'availability':'not_confirmed', 'observations':[], 'related':[]})
    return jobs


def market(jobs, comparison):
    current = datetime.now(timezone.utc)
    months = []
    for month in sorted({j['source_posted_at'][:7] for j in jobs}):
        in_progress = month == current.strftime('%Y-%m')
        if comparison == 'completed' and in_progress:
            continue
        rows = [j for j in jobs if j['source_posted_at'].startswith(month)]
        if comparison == 'elapsed':
            rows = [j for j in rows if datetime.fromisoformat(j['source_posted_at']).day <= current.day]
        counts = Counter(s['id'] for j in rows for s in j['skills'])
        months.append({'month':month,'denominator':len(rows),'counts':dict(counts),'percentages':{k:round(v/len(rows)*100,2) for k,v in counts.items()},'in_progress':in_progress,'complete':True,'retention_truncated':False,'coverage':{'processed':len(rows),'total':len(rows)}})
    return {'months':months,'skills':sorted({s['id'] for j in jobs for s in j['skills']}),'record_scope':'published_unexpired','notice':'Invented demonstration data. Live market statistics will come from MexicoDev. Expired jobs are purged.'}
