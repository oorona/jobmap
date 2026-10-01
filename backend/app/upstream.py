"""MexicoDev jobs-v1 transport adaptation, without new source judgments."""
from copy import deepcopy


def job_record(record):
    out = deepcopy(record)
    if not out.get('title'):
        out['title'] = 'Multiple roles' if out.get('role_kind') == 'multiple_roles' else 'Role title not stated'
    aliases = {'learning_support':'learning', 'adjacent_experience':'adjacent', 'working_conditions':'conditions'}
    dims = {}
    for name, dimension in out.get('dimensions', {}).items():
        score = dimension.get('score')
        # Producer jobs-v1 uses four ordered criteria, indexed 0 through 3.
        if dimension.get('rubric_version') == 'jobs-v1' and score is not None:
            if not 0 <= score <= 3:
                raise ValueError('Invalid jobs-v1 dimension score')
            dimension['score'] = score / 3
        dims[aliases.get(name, name)] = dimension
    out['dimensions'] = dims
    worldwide = out.get('worldwide') or {}
    countries = out.get('eligible_countries') or {}
    if worldwide.get('status') == 'stated' and worldwide.get('value') is True and countries.get('status', 'unknown') == 'unknown':
        out['eligible_countries'] = {**worldwide, 'value':['worldwide']}
    return out


def comparison_param(comparison):
    return 'month_to_date' if comparison == 'elapsed' else 'completed'


def market_record(data, comparison):
    months = []
    for month in data['months']:
        if comparison != 'all' and not month['included']:
            continue
        coverage = month.get('coverage') or {}
        months.append({**month, 'complete':coverage.get('complete', False),
                       'counts':{s['id']:s['count'] for s in month['skills']},
                       'percentages':{s['id']:s['percent'] or 0 for s in month['skills']}})
    return {**data, 'months':sorted(months, key=lambda m:m['month']),
            'skills':sorted({s['id'] for m in months for s in m['skills']}), 'notice':data.get('note', '')}
