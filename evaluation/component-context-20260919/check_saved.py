"""Offline assertions for the four final stage-2 saved-evidence controls."""
import json
import sys
from pathlib import Path

from retest import HERE, ROOT, digest, read

sys.path.insert(0, str(ROOT / 'iris-backend'))
from pipeline.component_context import dates


def check(case_id):
    data = read(HERE / 'final' / (case_id + '-input.json'))
    saved = read(HERE / 'final' / (case_id + '.json'))
    result = saved['review']
    assert saved['input_sha256'] == digest(data), 'Input integrity mismatch'
    assert result['status'] == 'ok', 'Technical error'
    assert result['original_claim'] == data['claim'], 'Original assertion changed'
    assert len(result['components']) == 1, 'Incomplete/extra fragment'
    part = result['components'][0]
    assert part['component'] == data['claim'], 'Dropped or rewritten words'
    assert not part['context']['context_is_evidence'], 'Post treated as evidence'
    for refs in part['context']['anchors'].values():
        for ref in refs:
            original = data['claim'] if ref['origin'] == 'claim' else data['source_context']
            assert original[ref['start']:ref['end']] == ref['quote'], 'Ungrounded reference'
    articles = {a['url']: a['text'] for a in data['articles']}
    for citation in part['citations']:
        assert ' '.join(citation['quote'].split()) in ' '.join(articles[citation['url']].split())
    assert result['verdict'] == ('Verified' if case_id == 'B12' else 'Not Found'), 'Unexpected verdict'
    if case_id != 'B12':
        assert not result['supporting_urls'], 'Unrelated evidence retained'
    else:
        assert result['supporting_urls'], 'No evidence for positive verdict'
    if case_id in {'A09', 'C07'}:
        times = ' '.join(r['quote'] for r in part['context']['anchors']['time'])
        assert (9, 9 if case_id == 'A09' else 17) in dates(times), 'Required event date lost'
    if case_id == 'C07':
        assert (10, 4) not in dates(times), 'Concert date replaced interview date'
        assert any(r['origin'] == 'source_context' for r in part['context']['anchors']['event'])
        sources = [s for g in result['event_identity_checks'] for s in g['sources'].values()]
        assert sources and all(s['context_status'] != 'matching' for s in sources), 'Wrong event credited'
    return {'case_id': case_id, 'status': 'passed', 'verdict': result['verdict']}


if __name__ == '__main__':
    results = []
    for case_id in ['B05', 'B12', 'A09', 'C07']:
        try:
            results.append(check(case_id))
        except (AssertionError, KeyError, OSError) as error:
            results.append({'case_id': case_id, 'status': 'failed', 'reason': str(error)})
    print(json.dumps(results, indent=2))
    raise SystemExit(any(r['status'] != 'passed' for r in results))
