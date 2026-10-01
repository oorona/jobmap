"""Dependency-free IR metrics with explicit handling of missing judgments."""
import math
import random
import statistics


def unique(rows):
    seen=set();out=[]
    for row in rows:
        if row['id'] not in seen:
            out.append(row);seen.add(row['id'])
    return out


def metrics(rows, grades, k=10, complete_corpus=False):
    rows=unique(rows)[:k]
    if any(r['id'] not in grades for r in rows):
        return None  # Missing labels must not become negative judgments.
    values=[grades[r['id']] for r in rows]
    relevant=sum(v>0 for v in values)
    positives=sum(v>0 for v in grades.values())
    dcg=sum((2**v-1)/math.log2(rank+2) for rank,v in enumerate(values))
    ideal=sorted(grades.values(),reverse=True)[:k]
    idcg=sum((2**v-1)/math.log2(rank+2) for rank,v in enumerate(ideal))
    return {'precision':relevant/k,'ndcg':dcg/idcg if idcg else None,
            'recall':relevant/positives if complete_corpus and positives else None,
            'reciprocal_rank':next((1/(i+1) for i,v in enumerate(values) if v>0),0) if positives else None,
            'returned':len(rows),'relevant_returned':relevant,'no_match':positives==0,
            'no_match_false_positive':bool(rows) if complete_corpus and positives==0 else None}


def quantile(values,p):
    if not values:return None
    values=sorted(values);position=(len(values)-1)*p;lower=int(position)
    return values[lower]+(values[min(lower+1,len(values)-1)]-values[lower])*(position-lower)


def mean(values):
    values=[v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def paired_interval(left,right,seed=20261001,iterations=2000):
    ids=sorted(set(left)&set(right));diffs=[left[i]-right[i] for i in ids if left[i] is not None and right[i] is not None]
    if len(diffs)<2:return None
    rng=random.Random(seed)
    samples=[statistics.fmean(rng.choices(diffs,k=len(diffs))) for _ in range(iterations)]
    return {'mean_difference':statistics.fmean(diffs),'lower_95':quantile(samples,.025),'upper_95':quantile(samples,.975),'queries':len(diffs),'procedure':'paired query bootstrap, 2000 resamples'}


def choose_threshold(observations,qrels):
    """Maximize macro F1 on development queries only; no-match queries reward abstention."""
    candidates={-1.000001,1.000001}
    for obs in observations:
        candidates.update(row['relevance'] for row in obs['results'])
    candidates.add(max(candidates)+.000001)
    best=None
    for threshold in sorted(candidates):
        values=[]
        for obs in observations:
            grades=qrels[obs['query_id']]
            positives={ident for ident,grade in grades.items() if grade>0}
            selected={r['id'] for r in obs['results'] if r['relevance']>=threshold}
            hits=len(selected&positives)
            f1=2*hits/(len(selected)+len(positives)) if selected or positives else 1.0
            values.append(f1)
        score=mean(values)
        # Prefer the higher cutoff on equal validation performance.
        if best is None or score>=best['dev_macro_f1']:
            best={'threshold':threshold,'dev_macro_f1':score}
    return best
