"""Fresh, sequential full-request baseline; no production edits or verdict cache writes."""
import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from collect import HERE, ROOT, read, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', nargs='*')
    args = parser.parse_args()
    folder = HERE / 'current-baseline'
    folder.mkdir(exist_ok=True)
    expected = read(HERE / 'baseline-manifest.json')['production_hashes']
    for name, digest in expected.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Production baseline changed: ' + name)
    sys.path.insert(0, str(ROOT / 'iris-backend'))
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'iris-backend/.env')
    import app
    from iris_trace.web import configuration
    logging.basicConfig(filename=folder / 'services.log', level=logging.INFO, force=True)
    app.app.config.update(IRIS_TRACE_ENABLED=True, IRIS_TRACE_ARTIFACTS=True,
                          IRIS_TRACE_PATH=str(folder / 'traces.sqlite3'))
    config = configuration(app.app)
    config['effective_models'] = {key: os.getenv(key, default) for key, default in [
        ('OPENAI_MODEL', 'gpt-4o-mini'), ('IRIS_CLAIM_REVIEW_MODEL', 'gpt-4.1-2025-04-14'),
        ('IRIS_EVIDENCE_REVIEW_MODEL', 'gpt-4.1-2025-04-14')]}
    if not (folder / 'configuration.json').exists():
        write(folder / 'configuration.json', config)
    cases = read(HERE / 'cases.json')
    with patch.object(app, 'get_cached_verdict', return_value=None), \
         patch.object(app, 'save_cached_verdict', return_value=None):
        for case in cases:
            if args.cases and case['id'] not in args.cases:
                continue
            target = folder / (case['id'] + '.json')
            if target.exists():
                print('PRESERVED ' + case['id'], flush=True)
                continue
            print('START ' + case['id'], flush=True)
            started = datetime.now(timezone.utc).isoformat()
            before = time.monotonic()
            try:
                with app.app.test_client() as client:
                    response = client.post('/verify', json={'text': case['text'], 'debug': True,
                                                            'platform': 'audit-baseline'})
                body = response.get_json()
                result = {'case_id': case['id'], 'input_sha256': case['input_sha256'],
                          'started_utc': started, 'http_status': response.status_code,
                          'seconds': round(time.monotonic() - before, 3),
                          'trace_id': response.headers.get('X-IRIS-Trace-ID'),
                          'cache_policy': 'reads and writes bypassed', 'cache_version': app.RESULT_CACHE_VERSION,
                          'response': body}
            except Exception as error:
                result = {'case_id': case['id'], 'started_utc': started,
                          'seconds': round(time.monotonic() - before, 3), 'http_status': None,
                          'harness_error': type(error).__name__, 'response': None}
            finally:
                store = app.app.extensions.get('iris_trace_store')
                if store:
                    store.flush()
            write(target, result)
            body = result.get('response') or {}
            print(json.dumps({'case': case['id'], 'http': result['http_status'], 'seconds': result['seconds'],
                              'verdicts': [c.get('verdict') for c in body.get('claims', [])] or [body.get('verdict')],
                              'reason': body.get('reason_code'), 'stage': body.get('failed_stage')}), flush=True)
            time.sleep(3 if result['http_status'] == 200 else 15)
    store = app.app.extensions.get('iris_trace_store')
    if store:
        store.close()
    print('BASELINE FINISHED', flush=True)


if __name__ == '__main__':
    main()
