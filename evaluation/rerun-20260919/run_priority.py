"""
Fresh sequential rerun of the priority regression cases against the current code.

Same request path and envelope as full-pipeline-audit-20260918/run_baseline.py,
written to this folder so the 18 September baseline is never overwritten.
Verdict-cache reads and writes are bypassed; TRACE captures every request.

    python evaluation/rerun-20260919/run_priority.py            # all priority cases
    python evaluation/rerun-20260919/run_priority.py --cases C02 # selected cases
"""
import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUDIT = ROOT / 'evaluation' / 'full-pipeline-audit-20260918'
RESULTS = HERE / 'results'

PASSED_ON_0918 = ['A01', 'A04', 'A10', 'B02', 'B03', 'B06', 'B09', 'B10', 'B11', 'B13', 'B14', 'C01', 'C05']
STEP3_TARGETS = ['C02', 'C03', 'B15']
RETRIEVAL_TARGETS = ['C04']
PRIORITY = PASSED_ON_0918 + STEP3_TARGETS + RETRIEVAL_TARGETS


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', nargs='*')
    parser.add_argument('--out', default='results', help='result folder name inside this directory')
    parser.add_argument('--variants', help='JSON file of extra inputs [{id, text, note}] to run as well')
    args = parser.parse_args()
    results = HERE / args.out
    results.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ROOT / 'iris-backend'))
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'iris-backend' / '.env')
    import app
    from iris_trace.web import configuration

    logging.basicConfig(filename=HERE / 'services.log', level=logging.INFO, force=True)
    app.app.config.update(IRIS_TRACE_ENABLED=True, IRIS_TRACE_ARTIFACTS=True,
                          IRIS_TRACE_PATH=str(HERE / 'traces.sqlite3'))
    config = configuration(app.app)
    config['effective_models'] = {key: os.getenv(key, default) for key, default in [
        ('OPENAI_MODEL', 'gpt-4o-mini'), ('IRIS_CLAIM_REVIEW_MODEL', 'gpt-4.1-2025-04-14'),
        ('IRIS_EVIDENCE_REVIEW_MODEL', 'gpt-4.1-2025-04-14')]}
    config['git_commit'] = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                                          text=True).stdout.strip()
    config['cache_version'] = app.RESULT_CACHE_VERSION
    write(HERE / 'configuration.json' if args.out == 'results' else results / 'configuration.json', config)

    cases = {case['id']: case for case in read(AUDIT / 'cases.json')}
    selected = [ident for ident in PRIORITY if not args.cases or ident in args.cases]
    if args.variants:
        for variant in read(HERE / args.variants):
            cases[variant['id']] = {**variant, 'input_sha256': hashlib.sha256(variant['text'].encode('utf-8')).hexdigest()}
            selected.append(variant['id'])
    with patch.object(app, 'get_cached_verdict', return_value=None), \
         patch.object(app, 'save_cached_verdict', return_value=None):
        for ident in selected:
            case = cases[ident]
            target = results / f'{ident}.json'
            if target.exists():
                print('PRESERVED ' + ident, flush=True)
                continue
            print('START ' + ident, flush=True)
            started = datetime.now(timezone.utc).isoformat()
            before = time.monotonic()
            try:
                with app.app.test_client() as client:
                    response = client.post('/verify', json={'text': case['text'], 'debug': True,
                                                            'platform': 'rerun-20260919'})
                result = {'case_id': ident, 'input_sha256': case['input_sha256'], 'started_utc': started,
                          'http_status': response.status_code, 'seconds': round(time.monotonic() - before, 3),
                          'trace_id': response.headers.get('X-IRIS-Trace-ID'),
                          'cache_policy': 'reads and writes bypassed', 'cache_version': app.RESULT_CACHE_VERSION,
                          'response': response.get_json()}
            except Exception as error:
                result = {'case_id': ident, 'input_sha256': case['input_sha256'], 'started_utc': started,
                          'seconds': round(time.monotonic() - before, 3), 'http_status': None,
                          'harness_error': f'{type(error).__name__}: {error}', 'response': None}
            finally:
                store = app.app.extensions.get('iris_trace_store')
                if store:
                    store.flush()
            write(target, result)
            body = result.get('response') or {}
            print(json.dumps({'case': ident, 'http': result['http_status'], 'seconds': result['seconds'],
                              'verdicts': [c.get('verdict') for c in body.get('claims', [])] or [body.get('verdict')]},
                             ensure_ascii=False), flush=True)
            time.sleep(3 if result['http_status'] == 200 else 15)

    store = app.app.extensions.get('iris_trace_store')
    if store:
        store.close()
    print('RERUN FINISHED', flush=True)


if __name__ == '__main__':
    main()
