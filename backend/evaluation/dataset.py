"""Fictional postings and fact-derived labels, fixed before any model results."""
import hashlib
import json

TOPICS = [
 ('robotics','Robotics engineer',['robotics','ros2','c++'],'Build autonomous warehouse robots. Develop motion planning, localization and manipulation software. Test navigation on physical machines.', 'I want to make machines navigate warehouses and pick up physical objects.', 'robotics engineering jobs', 'dev'),
 ('backend','Backend engineer',['python','fastapi','postgresql'],'Build Python HTTP APIs and PostgreSQL services. Own authentication, billing endpoints and database migrations.', 'I want to build the server side of web products, including endpoints and relational databases.', 'Python backend engineer', 'test'),
 ('frontend','Frontend engineer',['react','typescript','css'],'Build React and TypeScript browser interfaces. Own accessible forms, client-side state and responsive web layouts.', 'I want to build accessible interactive interfaces that people use in a web browser.', 'React frontend engineer', 'dev'),
 ('infra','Platform engineer',['kubernetes','terraform','linux'],'Run Kubernetes clusters and Terraform infrastructure. Own deployment pipelines, incident on-call and Linux reliability.', 'I want to keep container clusters and cloud deployments reliable and respond to outages.', 'Kubernetes infrastructure engineer', 'test'),
 ('analytics','Analytics engineer',['sql','dbt','python'],'Build SQL and dbt business data models. Maintain revenue dashboards, data quality checks and financial reporting.', 'I want to transform business data into reliable revenue reports and dashboards.', 'SQL dbt analytics engineer', 'test'),
 ('ml','Machine learning engineer',['python','pytorch','machine-learning'],'Train and deploy PyTorch machine learning models. Own model evaluation, feature pipelines and production inference.', 'I want to train predictive models and put them into production with evaluation and monitoring.', 'PyTorch machine learning engineer', 'dev'),
 ('security','Security engineer',['security','incident-response','siem'],'Investigate security alerts and respond to intrusions. Build detection rules, threat hunting and incident response playbooks.', 'I want to investigate intrusions and build defenses against attackers.', 'Security incident response engineer', 'test'),
 ('mobile','iOS engineer',['swift','ios','swiftui'],'Build native iPhone applications using Swift and SwiftUI. Own mobile notifications, offline storage and App Store releases.', 'I want to build native apps for iPhones, including offline behavior and store releases.', 'Swift iOS mobile engineer', 'test'),
 ('embedded','Firmware engineer',['c++','embedded','microcontrollers'],'Write C++ firmware for microcontrollers. Develop hardware drivers, debug boards and implement real-time sensor protocols.', 'I want to write software that runs directly on tiny chips and communicates with sensors.', 'C++ microcontroller firmware engineer', 'dev'),
 ('tools','Developer tools engineer',['rust','compiler','cli'],'Build Rust command-line tools and compiler diagnostics. Work on parsers, incremental compilation and developer build performance.', 'I want to improve compilers and command-line tools that other programmers use to build software.', 'Rust compiler developer tools engineer', 'test'),
 ('devrel','Developer educator',['documentation','teaching','sdk'],'Teach developers through workshops and technical tutorials. Write SDK guides, example applications and educational documentation.', 'I want to teach other programmers through tutorials, workshops and working code examples.', 'Developer education documentation jobs', 'test'),
 ('design','Product designer',['figma','ux','research'],'Conduct user research and design product workflows in Figma. Test prototypes, run usability interviews and maintain design systems.', 'I want to interview users and design and test product experiences and prototypes.', 'UX product designer user research', 'test'),
]
VARIANTS = [
 {'mode':'remote','country':'worldwide','seniority':'junior','contract':'full-time','pay':90000,'degree':False,'place':'any country including Mexico'},
 {'mode':'remote','country':'US','seniority':'senior','contract':'full-time','pay':180000,'degree':True,'place':'the United States only'},
 {'mode':'onsite','country':'DE','seniority':'senior','contract':'contract','pay':130000,'degree':True,'place':'Berlin, Germany'},
 {'mode':'hybrid','country':'GB','seniority':'mid-level','contract':'full-time','pay':110000,'degree':False,'place':'London, United Kingdom'},
 {'mode':'remote','country':'worldwide','seniority':'senior','contract':'full-time','pay':220000,'degree':False,'place':'any country including Mexico'},
 {'mode':'onsite','country':'MX','seniority':'junior','contract':'internship','pay':60000,'degree':True,'place':'Mexico City, Mexico'},
]


def checksum(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def controlled():
    jobs=[];queries=[];qrels={}
    for n,(topic,title,skills,work,natural,keyword,split) in enumerate(TOPICS):
        for index, facts in enumerate(VARIANTS):
            ident=f'synthetic_{topic}_{index}'
            experience='No professional experience is required; this is an entry-level role with mentoring.' if facts['seniority']=='junior' else 'Requires five years of professional experience.' if facts['seniority']=='senior' else 'Requires two years of professional experience.'
            degree='A university degree is required.' if facts['degree'] else 'No university degree is required.'
            document=f"{title}. {work} This is a {facts['seniority']} {facts['contract']} position. Work arrangement: {facts['mode']}. Applicants must work from {facts['place']}. {experience} {degree} Annual compensation is exactly USD {facts['pay']:,}; higher pay is not offered."
            assert len(document)<=1000
            jobs.append({'id':ident,'title':title,'company':{'id':ident,'name':f'Fictional team {n+1}-{index+1}'},'skills':[{'id':s,'label':s} for s in skills],
                'search_text':document,'description_text':document,'content_version':checksum(document),'expires_at':'2099-01-01T00:00:00+00:00',
                'work_mode':{'status':'stated','value':facts['mode']},'eligible_countries':{'status':'stated','value':[facts['country']]},'dimensions':{},
                'facts':{'topic':topic,**facts}})
        variants=[('keywords',keyword,lambda f:True),('intent',natural,lambda f:True),
                  ('constraints',f'I want a junior {title.lower()} role, fully remote from Mexico, with no university degree required.',lambda f:f['seniority']=='junior' and f['mode']=='remote' and f['country']=='worldwide' and not f['degree'])]
        if n%2:
            variants.append(('no_match',f'I want a {title.lower()} job paying at least USD 400,000 per year.',lambda f:f['pay']>=400000))
        else:
            variants.append(('exclusion',f'I want a senior {title.lower()} job that lets me work remotely from Mexico. Exclude jobs restricted to US residents.',lambda f:f['seniority']=='senior' and f['mode']=='remote' and f['country']=='worldwide'))
        for kind,query,predicate in variants:
            qid=f'{topic}_{kind}'
            queries.append({'id':qid,'query':query,'category':kind,'split':split,'topic':topic})
            qrels[qid]={job['id']:2 if job['facts']['topic']==topic and predicate(job['facts']) else 0 for job in jobs if job['facts']['topic']==topic}
    for grades in qrels.values():
        for job in jobs:
            grades.setdefault(job['id'],0)
    data={'name':'job-search-controlled-v1','kind':'synthetic','jobs':jobs,'queries':queries,'qrels':qrels,
          'label_source':'Deterministic explicit job facts, authored before inference. No model supplied relevance labels.',
          'limitations':'Fictional, English, short templated postings; labels test stated requirements. Not a production accuracy estimate. Development and test topics are disjoint.'}
    data['hash']=checksum(data)
    return data


def live_queries():
    # Same predefined intentions; no queries selected after seeing system outcomes.
    return [{**q,'split':'unlabeled'} for q in controlled()['queries']]
