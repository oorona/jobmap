"""Produce an HTML report, machine-readable metrics, and a blind grading workbench."""
import argparse
import csv
import html
import json
import random
from collections import defaultdict
from pathlib import Path
from .metrics import metrics,mean,quantile,paired_interval,choose_threshold

NAMES={'jev':'Jev deployed','jev_pipeline':'Jev deployed pipeline','jev_shared':'Jev · same corpus/text','minilm':'MiniLM','bge':'BGE','arctic':'Arctic','bm25':'BM25 keywords','minilm_jev':'MiniLM → Jev top 20'}


def pool(run):
    jobs={j['id'] for j in run['dataset']['jobs']};pairs=defaultdict(set)
    for observation in run['observations']:
        if observation['repeat']==0 and observation['available']:
            pairs[observation['query_id']].update(r['id'] for r in observation['results'][:10])
    rng=random.Random(run['seed'])
    for qid in sorted(pairs):
        others=sorted(jobs-pairs[qid]);pairs[qid].update(rng.sample(others,min(2,len(others))))
    return pairs


def load_labels(run,paths):
    known_queries={q['id'] for q in run['dataset']['queries']};known_jobs={j['id'] for j in run['dataset']['jobs']}
    judgments=defaultdict(list)
    for path in paths:
        data=json.loads(Path(path).read_text())
        if data.get('run_id')!=run['run_id'] or data.get('dataset_hash')!=run['dataset']['hash']:
            raise ValueError('Labels belong to a different run or corpus')
        for item in data['judgments']:
            if item['query_id'] not in known_queries or item['job_id'] not in known_jobs or type(item['grade']) is not int or item['grade'] not in (0,1,2):
                raise ValueError('Invalid judgment')
            judgments[(item['query_id'],item['job_id'])].append(item['grade'])
    grades=defaultdict(dict);conflicts=0
    for (query,job),values in judgments.items():
        if len(set(values))==1:grades[query][job]=values[0]
        else:conflicts+=1
    return dict(grades),conflicts


def analyze(run,label_paths=()):
    dataset=run['dataset'];synthetic=dataset['kind']=='synthetic'
    label_files=[json.loads(Path(p).read_text()) for p in label_paths] if not synthetic else []
    llm=any(data.get('label_source')=='llm' for data in label_files)
    grades=dataset['qrels'] if synthetic else load_labels(run,label_paths)[0]
    conflicts=0 if synthetic else load_labels(run,label_paths)[1]
    order=['jev','jev_pipeline','jev_shared','minilm','bge','arctic','bm25','minilm_jev']
    methods=sorted({o['method'] for o in run['observations']},key=lambda m:order.index(m) if m in order else len(order))
    queries={q['id']:q for q in dataset['queries']};primary={(o['method'],o['query_id']):o for o in run['observations'] if o['repeat']==0}
    complete={qid for qid in queries if all(primary.get((method,qid),{}).get('available') for method in methods)}
    if not synthetic:
        complete&={qid for qid,ids in pool(run).items() if ids<=set(grades.get(qid,{}))}
    test={qid for qid in complete if not synthetic or queries[qid]['split']=='test'}
    positive={qid for qid in test if any(v>0 for v in grades.get(qid,{}).values())}
    summary={'run_id':run['run_id'],'dataset_hash':dataset['hash'],'track':run['track'],'run_complete':run['complete'],
             'corpus_jobs':len(dataset['jobs']),'queries':len(queries),'quality_queries':len(positive),'judged_test_queries':len(test),
             'human_label_conflicts':conflicts,'quality_status':'controlled synthetic evidence' if synthetic else ('LLM-judged pooled evidence (provisional)' if llm else 'human-judged pooled evidence') if positive else ('pending complete LLM judgments' if llm else 'pending human judgments'),
             'api_committed_usd':run.get('committed_api_usd'), 'shared_usage_delta_usd':run.get('shared_usage_delta_usd'),
             'methods':{},'per_query':{},'judged_result_counts':{},'paired_comparisons':[],'limitations':dataset['limitations']}
    if not synthetic:
        for qid in sorted(test):
            summary['judged_result_counts'][qid]={'query':queries[qid]['query'],'methods':{}}
            for method in methods:
                results=primary[(method,qid)]['results'][:10]
                summary['judged_result_counts'][qid]['methods'][method]={
                    'strong_top10':sum(grades[qid].get(r['id'])==2 for r in results),
                    'partial_top10':sum(grades[qid].get(r['id'])==1 for r in results),
                    'irrelevant_top10':sum(grades[qid].get(r['id'])==0 for r in results),
                    'returned_top10':len(results),
                    'strong_precision_at_5':sum(grades[qid].get(r['id'])==2 for r in results[:5])/5,
                    'precision_at_5':sum(grades[qid].get(r['id'],0)>0 for r in results[:5])/5}
    summary['judgment_sources']=[{'source':d.get('label_source','human'),'judge':d.get('judge')} for d in label_files]
    if llm:
        summary['limitations']+=' Labels are automated model opinions, not human ground truth. Judge errors and bias can affect every method. Partial matches count toward ordinary precision; strong-match precision requires grade 2.'
    for method in methods:
        observations=[o for o in run['observations'] if o['method']==method]
        successes=[o for o in observations if o['available']]
        per_query={}
        for qid in sorted(positive):
            obs=primary[(method,qid)]
            at5=metrics(obs['results'],grades[qid],5,synthetic);at10=metrics(obs['results'],grades[qid],10,synthetic)
            per_query[qid]={'precision_at_5':at5['precision'],'ndcg_at_10':at10['ndcg'],'recall_at_10':at10['recall'],'mrr_at_10':at10['reciprocal_rank'],
                            'strong_precision_at_5':sum(grades[qid].get(r['id'])==2 for r in obs['results'][:5])/5,
                            'strong_matches_at_10':sum(grades[qid].get(r['id'])==2 for r in obs['results'][:10])}
        result={'name':NAMES.get(method,method),'attempts':len(observations),'successes':len(successes),'failures':len(observations)-len(successes),
                'latency_p50_ms':quantile([o['elapsed_ms'] for o in successes],.5),'latency_p95_ms':quantile([o['elapsed_ms'] for o in successes],.95),
                'precision_at_5':mean([m['precision_at_5'] for m in per_query.values()]),'ndcg_at_10':mean([m['ndcg_at_10'] for m in per_query.values()]),
                'recall_at_10':mean([m['recall_at_10'] for m in per_query.values()]),'mrr_at_10':mean([m['mrr_at_10'] for m in per_query.values()]),
                'strong_precision_at_5':mean([m['strong_precision_at_5'] for m in per_query.values()]),
                'strong_matches_at_10':mean([m['strong_matches_at_10'] for m in per_query.values()]),'categories':{}}
        for category in sorted({q['category'] for q in queries.values()}):
            case=[v for qid,v in per_query.items() if queries[qid]['category']==category]
            result['categories'][category]={'queries':len(case),'ndcg_at_10':mean([v['ndcg_at_10'] for v in case])}
        if synthetic:
            development=[o for o in observations if o['repeat']==0 and o['split']=='dev' and o['available']]
            if len(development)==sum(q['split']=='dev' for q in queries.values()):
                tuned=choose_threshold(development,grades);result['calibration']=tuned
                f1s=[];false_positives=[]
                for qid in test:
                    positive_ids={ident for ident,grade in grades[qid].items() if grade>0}
                    selected={r['id'] for r in primary[(method,qid)]['results'] if r['relevance']>=tuned['threshold']}
                    hits=len(positive_ids&selected)
                    f1s.append(2*hits/(len(positive_ids)+len(selected)) if positive_ids or selected else 1)
                    if not positive_ids:false_positives.append(bool(selected))
                result['calibrated_test_macro_f1']=mean(f1s)
                result['no_match_queries']=len(false_positives)
                result['no_match_false_positive_rate']=mean(false_positives)
            stability=[]
            for qid in queries:
                repeats=[o for o in successes if o['query_id']==qid]
                if len(repeats)>1:
                    first={r['id'] for r in repeats[0]['results'][:10]}
                    for repeat in repeats[1:]:
                        other={r['id'] for r in repeat['results'][:10]}
                        stability.append(len(first&other)/len(first|other) if first|other else 1)
            result['top10_repeat_jaccard']=mean(stability)
            result['api_usd']=sum(o.get('api_usd') or 0 for o in successes)
            result['unknown_charge_calls']=sum(o.get('api_usd') is None for o in successes)
        summary['methods'][method]=result;summary['per_query'][method]=per_query
    if synthetic:
        dev_quality={}
        for method in ('minilm','bge','arctic'):
            dev_quality[method]=mean([metrics(primary[(method,qid)]['results'],grades[qid],10,True)['ndcg'] for qid in complete if queries[qid]['split']=='dev' and any(grades[qid].values())])
        if all(v is not None for v in dev_quality.values()):
            best=max(dev_quality,key=dev_quality.get);summary['embedding_selected_on_dev']=best
            reference={q:v['ndcg_at_10'] for q,v in summary['per_query'][best].items()}
            for method in ('jev_pipeline','jev_shared','minilm_jev','bm25'):
                candidate={q:v['ndcg_at_10'] for q,v in summary['per_query'].get(method,{}).items()}
                interval=paired_interval(candidate,reference)
                if interval:summary['paired_comparisons'].append({'method':method,'reference':best,**interval})
    return summary


def number(value,percent=False):
    return '—' if value is None else f'{value*100:.1f}%' if percent else f'{value:.2f}'


def render(run,summary,directory):
    escape=html.escape
    rows=[]
    for method,result in summary['methods'].items():
        rows.append('<tr>'+''.join(f'<td>{escape(str(value))}</td>' for value in [result['name'],number(result['precision_at_5'],True),number(result['ndcg_at_10']),number(result['recall_at_10'],True),number(result['latency_p50_ms']),number(result['latency_p95_ms']),f"{result['successes']}/{result['attempts']}"] )+'</tr>')
    calibrated=''
    if run['track']=='controlled':
        calibrated='<h2>Cutoffs chosen on development queries</h2><p>Macro F1 rewards correct abstention as 1 on no-match queries. Ranking metrics above use no cutoff and exclude no-match queries. Unfilled top-k positions count as misses. API costs exclude CPU, storage, and indexing; charges use the application’s configured accounting rate.</p><table><tr><th>Method</th><th>Dev cutoff</th><th>Held-out macro F1</th><th>No-match false-positive rate</th><th>Recorded API USD</th></tr>'
        for result in summary['methods'].values():
            calibrated+='<tr>'+''.join('<td>'+escape(str(x))+'</td>' for x in [result['name'],number(result.get('calibration',{}).get('threshold')),number(result.get('calibrated_test_macro_f1'),True),number(result.get('no_match_false_positive_rate'),True),f"{result.get('api_usd',0):.6f}"])+'</tr>'
        calibrated+='</table><h2>Paired held-out nDCG differences</h2><p>The reference embedding was selected on development queries. Positive differences favor the listed method. Intervals resample queries, not reviewers; this small synthetic suite does not establish production superiority.</p><ul>'
        for row in summary['paired_comparisons']:
            calibrated+=f"<li>{escape(NAMES[row['method']])} minus {escape(NAMES[row['reference']])}: {row['mean_difference']:+.3f}, 95% interval [{row['lower_95']:+.3f}, {row['upper_95']:+.3f}], {row['queries']} queries.</li>"
        calibrated+='</ul>'
    counts=''
    if summary.get('judged_result_counts'):
        counts='<h2>Relevant jobs per request</h2><p>Each cell shows strong / partial / irrelevant matches among the first ten returned jobs. Includes fully judged queries with no relevant jobs in the pool. This does not establish whether relevant jobs exist outside the pool.</p><div class="scroll"><table><tr><th>Request</th>'+''.join('<th>'+escape(r['name'])+'</th>' for r in summary['methods'].values())+'</tr>'
        for row in summary['judged_result_counts'].values():
            counts+='<tr><td>'+escape(row['query'])+'</td>'+''.join('<td>'+str(row['methods'][m]['strong_top10'])+' / '+str(row['methods'][m]['partial_top10'])+' / '+str(row['methods'][m]['irrelevant_top10'])+'</td>' for m in summary['methods'])+'</tr>'
        counts+='</table></div><p>Strong-match Precision@5 across all fully judged queries: '+', '.join(escape(summary['methods'][m]['name'])+' '+number(mean([r['methods'][m]['strong_precision_at_5'] for r in summary['judged_result_counts'].values()]),True) for m in summary['methods'])+'. Ranking metrics above exclude queries with no relevant job in the judged pool.</p>'
    queryrows=[]
    for query in run['dataset']['queries']:
        if run['track']=='controlled' and query['split']!='test':continue
        values=[query['query'],query['category']]+[number(summary['per_query'][method].get(query['id'],{}).get('ndcg_at_10')) for method in summary['methods']]
        queryrows.append('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in values)+'</tr>')
    judges=''
    if summary.get('judgment_sources'):
        judges='<h2>Judgment provenance</h2><p>Strong-match Precision@5 counts grade 2 only. The main table also counts partial matches (grade 1). Judge timing and token usage are separate from search latency.</p><ul>'+''.join('<li>'+escape(r['name'])+': strong-match Precision@5 '+number(r.get('strong_precision_at_5'),True)+', mean strong matches in top 10 '+number(r.get('strong_matches_at_10'))+'</li>' for r in summary['methods'].values())+'</ul><details><summary>Judge model and rubric</summary><pre style="white-space:pre-wrap">'+escape(json.dumps(summary['judgment_sources'],indent=2))+'</pre></details>'
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Job search benchmark</title><style>body{{font:15px/1.6 system-ui;max-width:1300px;margin:40px auto;padding:0 24px;color:#e7edf3;background:#0b1016}}h1,h2{{font-weight:500}}a{{color:#6cd9db}}.notice{{padding:18px;border:1px solid #54717a;background:#12232b;border-radius:8px}}table{{border-collapse:collapse;width:100%;margin:24px 0}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #293b48}}th{{color:#6cd9db}}.scroll{{overflow:auto}}code{{overflow-wrap:anywhere;font-size:12px}}details{{margin:24px 0}}small{{color:#9baebc}}</style>
<h1>Job search benchmark · {escape(run['track'])}</h1><div class="notice"><strong>{escape(summary['quality_status'])}</strong><br>{escape(summary['limitations'])}</div>
<p>{summary['corpus_jobs']} postings · {summary['queries']} queries · {run['repeats']} repeat(s) · {summary['quality_queries']} fully judged positive test queries used for quality.</p><p>Search run complete: {summary['run_complete']} · Run <code>{escape(run['run_id'])}</code><br>Dataset SHA-256: <code>{escape(summary['dataset_hash'])}</code></p>
<p><a href="summary.json">Download metrics JSON</a> · <a href="metrics.csv">Download metrics CSV</a> · <a href="blind-grade.html">Blind grading workbench</a></p>
<div class="scroll"><table><tr><th>Method</th><th>Precision@5</th><th>{'nDCG@10' if run['track']=='controlled' else 'Pooled nDCG@10'}</th><th>Recall@10</th><th>Median ms</th><th>p95 ms</th><th>Successes</th></tr>{''.join(rows)}</table></div>
<p>Quality uses the first repeat only. Missing judgments are not negative labels. Real-job corpus recall and no-match accuracy are withheld without exhaustive judgments. Latency percentiles pool queries and repeats; failures are reported separately. Local model API charges are zero, but hosting is not free.</p>
<div class="scroll">{calibrated}</div>{judges}{counts}<details><summary>Protocol and model versions</summary><pre style="white-space:pre-wrap">{escape(json.dumps({'models':run['models'],'encoding_version':run['encoding_version'],'protocol':run['methodology']},indent=2))}</pre></details>
<h2>Per-query nDCG</h2><div class="scroll"><table><tr><th>Query</th><th>Category</th>{''.join('<th>'+escape(v['name'])+'</th>' for v in summary['methods'].values())}</tr>{''.join(queryrows)}</table></div></html>'''
    (directory/'report.html').write_text(page)
    (directory/'summary.json').write_text(json.dumps(summary,indent=2))
    fields=['name','precision_at_5','ndcg_at_10','recall_at_10','latency_p50_ms','latency_p95_ms','successes','attempts']
    with (directory/'metrics.csv').open('w') as file:
        writer=csv.DictWriter(file,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(summary['methods'].values())


def blind(run,directory):
    pairs=pool(run);cases=[{'query_id':qid,'job_id':ident} for qid,ids in sorted(pairs.items()) for ident in sorted(ids)]
    random.Random(run['seed']).shuffle(cases)
    data={'run_id':run['run_id'],'dataset_hash':run['dataset']['hash'],'cases':cases,
          'queries':{q['id']:q['query'] for q in run['dataset']['queries']},
          'jobs':{j['id']:{'title':j['title'],'company':j['company']['name'],'text':j.get('description_text',j['search_text'])} for j in run['dataset']['jobs']}}
    # No rankings, scores, model identities or expected labels enter the blind HTML.
    payload=json.dumps(data,ensure_ascii=True).replace('<','\\u003c')
    template=Path(__file__).with_name('blind.html').read_text()
    (directory/'blind-grade.html').write_text(template.replace('__DATA__',payload))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input');parser.add_argument('--output',required=True);parser.add_argument('--labels',action='append',default=[])
    args=parser.parse_args();run=json.loads(Path(args.input).read_text());directory=Path(args.output);directory.mkdir(parents=True,exist_ok=True)
    summary=analyze(run,args.labels);render(run,summary,directory);blind(run,directory)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('per_query','methods')},indent=2))
    print(json.dumps(summary['methods'],indent=2))


if __name__=='__main__':main()
