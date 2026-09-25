"""Summarize observations without equating model judgments to reference truth."""
import argparse
import json
import sqlite3
from collections import Counter

from collect import HERE, capture, read, write

STAGES = {
    'translation': ['text.translation'], 'screening': ['text.profile'],
    'claim_extraction': ['claims.extract'], 'retrieval': ['retrieval.source_search'],
    'article_extraction': ['retrieval.article_extract'],
    'attribution': ['claim.attribution_gate'], 'evidence_review': ['claim.component_review'],
    'delivery': ['request.assemble']}


def summarize(case, run, db):
    trace = capture(db, run['trace_id']) if run.get('trace_id') else {}
    body = run.get('response') or {}
    outputs = []
    for claim in body.get('claims', []):
        review = claim.get('component_review') or {}
        outputs.append({'id': claim.get('claim_id'), 'text': claim.get('claim_text'),
                        'normalized': claim.get('normalized_claim'), 'type': claim.get('claim_type'),
                        'attribution': claim.get('attribution'), 'verdict': claim.get('verdict'),
                        'message': claim.get('message'), 'cache_hit': claim.get('cache_hit'),
                        'political': claim.get('politically_sensitive'), 'review': review,
                        'evidence_sources': claim.get('evidence_sources', [])})
    events = trace.get('events', [])
    dependencies = [a['value'] for a in trace.get('artifacts', []) if a['kind'] == 'dependency']
    stages = {}
    for name, ids in STAGES.items():
        found = [e for e in events if e.get('stage_id') in ids and e.get('kind') == 'span.end']
        saved = [d for d in dependencies if d.get('stage_id') in ids]
        stages[name] = {'recorded': bool(found), 'calls': len(found),
                        'dependency_records': len(saved), 'reached': bool(found or saved),
                        'execution_errors': sum(e.get('status') == 'error' for e in found),
                        'seconds': round(sum(e.get('duration_ms', 0) for e in found)/1000, 3)}
    searches = [d['output'] for d in dependencies if d.get('stage_id') == 'retrieval.source_search']
    extracts = [d['output'] for d in dependencies if d.get('stage_id') == 'retrieval.article_extract']
    search_urls = sorted({r['url'] for s in searches if isinstance(s, dict) for r in s.get('results', []) if isinstance(r, dict) and r.get('url')})
    extraction = [{'url': a.get('url'), 'status': a.get('status'), 'words': a.get('word_count'),
                   'error': a.get('error')} for a in extracts if isinstance(a, dict)]
    result = {'id': case['id'], 'http': run['http_status'], 'seconds': run['seconds'],
              'trace_id': run.get('trace_id'), 'capture': trace.get('trace', {}).get('capture_status'),
              'top_verdict': body.get('verdict'), 'error': body.get('reason_code'),
              'failed_stage': body.get('failed_stage'), 'claims': outputs,
              'ignored': body.get('ignored_segments', []), 'translated_text': body.get('translated_text'),
              'profile_route': body.get('content_profile_route'), 'stages': stages,
              'search_urls': search_urls, 'article_extraction': extraction,
              'service_search_errors': sum(s.get('status') not in {'ok'} for s in searches if isinstance(s,dict)),
              'runtime': [e.get('data') for e in events if e.get('kind') == 'runtime.configuration'],
              'extracted_claims': [d['output'] for d in dependencies if d.get('stage_id') == 'claims.extract'],
              'rate_limits': [e.get('data') for e in events if e.get('kind') == 'component.rate_limit']}
    snapshot = HERE / 'current-trace-snapshots'
    snapshot.mkdir(exist_ok=True)
    write(snapshot / (case['id'] + '.json'), trace)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    args = parser.parse_args()
    folder = HERE / 'current-baseline'
    cases = read(HERE / 'cases.json')
    dbpath = folder / 'traces.sqlite3'
    if not dbpath.exists():
        return
    results = []
    with sqlite3.connect(f'{dbpath.as_uri()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        for case in cases:
            path = folder / (case['id'] + '.json')
            if not path.exists():
                continue
            result = summarize(case, read(path), db)
            results.append(result)
            if args.case == case['id']:
                print(json.dumps(result, ensure_ascii=True, indent=2))
    write(HERE / 'observations.json', results)
    if not args.case:
        for r in results:
            print(json.dumps({'id':r['id'],'http':r['http'],'seconds':r['seconds'],
                              'claims':len(r['claims']), 'verdicts':[c['verdict'] for c in r['claims']] or [r['top_verdict']],
                              'error':r['error'],'capture':r['capture'], 'searches':r['stages']['retrieval']['calls']}))
        print('TOTAL',len(results),'HTTP',dict(Counter(r['http'] for r in results)))


if __name__ == '__main__':
    main()
