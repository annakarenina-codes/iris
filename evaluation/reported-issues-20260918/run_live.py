"""User-authorized full requests with fresh search, no verdict cache reuse/write."""
import argparse
import json
import sys
import time
import logging
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'iris-backend'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', nargs='+', required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'iris-backend/.env')
    import app
    folder = Path(__file__).parent / args.label
    folder.mkdir(exist_ok=True)
    logging.basicConfig(filename=folder / 'services.log', level=logging.INFO, force=True)
    app.app.config.update(IRIS_TRACE_ENABLED=True, IRIS_TRACE_ARTIFACTS=True,
                          IRIS_TRACE_PATH=str(folder / 'traces.sqlite3'))
    cases = json.loads((Path(__file__).parent / 'cases.json').read_text(encoding='utf-8'))
    with patch.object(app, 'get_cached_verdict', return_value=None), \
         patch.object(app, 'save_cached_verdict', return_value=None):
        for name in args.cases:
            start = time.monotonic()
            print('START ' + name, flush=True)
            with app.app.test_client() as client:
                response = client.post('/verify', json={'text': cases[name], 'debug': True,
                                                        'platform': 'calibration'})
            result = {'case': name, 'cache_version': app.RESULT_CACHE_VERSION,
                      'seconds': round(time.monotonic() - start, 2), 'http_status': response.status_code,
                      'headers': dict(response.headers), 'response': response.get_json()}
            (folder / (name + '.json')).write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding='utf-8')
            body = result['response'] or {}
            print(json.dumps({'case': name, 'seconds': result['seconds'], 'http_status': response.status_code,
                              'reason_code': body.get('reason_code'), 'failed_stage': body.get('failed_stage'),
                              'claims': [{'text': c.get('claim_text'), 'verdict': c.get('verdict')}
                                         for c in body.get('claims', [])]}), flush=True)
