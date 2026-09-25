"""Approved four-case saved-evidence review. Never searches or changes old results."""
import hashlib
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUDIT = HERE.parent / 'full-pipeline-audit-20260918'
TARGETS = {'B05': 0, 'B12': 1, 'A09': 0, 'C07': 1}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def fixture(case_id, index):
    baseline = read(AUDIT / 'current-baseline' / (case_id + '.json'))
    snapshot = read(AUDIT / 'current-trace-snapshots' / (case_id + '.json'))
    articles = {}
    for artifact in snapshot['artifacts']:
        dep = artifact.get('value', {})
        if artifact.get('kind') != 'dependency' or dep.get('stage_id') != 'retrieval.article_extract':
            continue
        article = dep.get('output', {})
        if (dep.get('complete') and article.get('status') == 'extracted'
                and isinstance(article.get('text'), str) and article['text'].strip()):
            articles.setdefault(article['url'], article)
    if not articles:
        raise RuntimeError('No complete saved article pool: ' + case_id)
    response = baseline['response']
    claim = response['claims'][index]
    return {'case_id': case_id, 'claim_index': index, 'claim': claim['claim_text'],
            'source_context': response.get('translated_text') or response['original_text'],
            'articles': list(articles.values()), 'old_verdict': claim['verdict'],
            'old_review': claim.get('component_review'), 'baseline_trace_id': baseline['trace_id'],
            'scope': 'Saved case article pool, not an exact replay of per-claim retrieval inputs.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', nargs='+', choices=list(TARGETS), default=list(TARGETS))
    parser.add_argument('--run', default='initial')
    args = parser.parse_args()
    output_dir = HERE if args.run == 'initial' else HERE / args.run
    output_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / 'iris-backend'))
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'iris-backend/.env')
    from pipeline.component_evidence import review_components
    from iris_trace.core import CURRENT, Store, Trace

    store = Store(output_dir / 'traces.sqlite3')
    try:
        for case_id, index in TARGETS.items():
            if case_id not in args.cases:
                continue
            target = output_dir / (case_id + '.json')
            if target.exists():
                print('PRESERVED ' + case_id, flush=True)
                continue
            data = fixture(case_id, index)
            write(output_dir / (case_id + '-input.json'), data)
            print('START ' + case_id + ' articles=' + str(len(data['articles'])), flush=True)
            trace = Trace(store, '/calibration/component-context',
                          {'text': data['claim'], 'platform': 'harness'}, artifact_capture=True)
            token = CURRENT.set(trace)
            started = time.monotonic()
            try:
                result = review_components(data['claim'], data['articles'], data['source_context'])
                trace.finish(result, http_status=200 if result['status'] == 'ok' else 503)
            finally:
                CURRENT.reset(token)
                store.flush()
            output = {'case_id': case_id, 'scope': data['scope'], 'trace_id': trace.id,
                'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'input_sha256': digest(data),
                'seconds': round(time.monotonic() - started, 3), 'old_verdict': data['old_verdict'],
                'cache': 'not used; direct component review', 'new_searches': 0,
                'models': {key: os.getenv(key, default) for key, default in [
                    ('OPENAI_MODEL', 'gpt-4o-mini'), ('IRIS_EVIDENCE_REVIEW_MODEL', 'gpt-4.1-2025-04-14')]},
                'code_sha256': {name: hashlib.sha256((ROOT / 'iris-backend/pipeline' / name).read_bytes()).hexdigest()
                                for name in ['component_context.py', 'component_evidence.py']},
                'review': result}
            write(target, output)
            print(json.dumps({'case': case_id, 'seconds': output['seconds'], 'status': result['status'],
                              'verdict': result['verdict'], 'stage': result.get('failed_stage')}), flush=True)
    finally:
        store.close()


if __name__ == '__main__':
    main()
