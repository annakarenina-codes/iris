"""Live HTTP-level regression for the two saved evidence-review crashes."""

import hashlib
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / 'iris-backend'
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(BACKEND)
from dotenv import load_dotenv
load_dotenv(BACKEND / '.env')
import app as iris
from iris_trace.core import CURRENT, Store, Trace

parser = argparse.ArgumentParser()
parser.add_argument('--output-name', default='component-review-retest')
args = parser.parse_args()
if not args.output_name or Path(args.output_name).name != args.output_name or args.output_name in {'.', '..'}:
    parser.error('output-name must be a directory name, not a path')
OUT = HERE / args.output_name
OUT.mkdir(exist_ok=False)
# Use one explicit calibration TRACE so cache bypass cannot be overwritten by HTTP middleware.
iris.app.config['IRIS_TRACE_ENABLED'] = False
store = Store(OUT / 'traces.sqlite3')
records = json.loads((HERE / 'observed_trace_records.json').read_text(encoding='utf-8'))
manifest = {'started_utc': datetime.now(timezone.utc).isoformat(),
            'scope': 'Fresh full /verify requests for cases 3 and 7; live external services.',
            'cache_policy': 'bypass reads and writes', 'cache_version': iris.RESULT_CACHE_VERSION,
            'model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            'coverage_review_model': os.getenv('IRIS_CLAIM_REVIEW_MODEL', 'gpt-4.1-2025-04-14'),
            'entailment_review_model': os.getenv('IRIS_EVIDENCE_REVIEW_MODEL', 'gpt-4.1-2025-04-14'),
            'review_code_sha256': hashlib.sha256((BACKEND / 'pipeline/component_evidence.py').read_bytes()).hexdigest()}
manifest['code_sha256'] = {name: hashlib.sha256((BACKEND / name).read_bytes()).hexdigest()
                           for name in ['app.py', 'pipeline/claim_extractor.py',
                                        'pipeline/claim_coverage.py', 'pipeline/content_profiler.py',
                                        'pipeline/component_evidence.py', 'pipeline/claim_context.py']}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
summary = []
try:
    for record in records:
        number = record['case']
        if number not in [3, 7]:
            continue
        payload = {'text': record['input']['text'], 'debug': True, 'platform': 'harness'}
        trace = Trace(store, '/verify', payload, True, True)
        token = CURRENT.set(trace)
        start = time.monotonic()
        print(f'START case {number}: {trace.id}', flush=True)
        try:
            response = iris.app.test_client().post('/verify', json=payload)
            result = response.get_json()
            trace.finish(result, response.status_code)
            captured = {'case': number, 'trace_id': trace.id, 'http_status': response.status_code,
                        'elapsed_seconds': round(time.monotonic()-start, 3), 'input': payload, 'output': result}
        except Exception as error:
            trace.finish({'error': type(error).__name__}, 500, error)
            captured = {'case': number, 'trace_id': trace.id, 'error_type': type(error).__name__}
        finally:
            CURRENT.reset(token)
        store.flush()
        (OUT / f'case-{number:02d}.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding='utf-8')
        item = {k: v for k, v in captured.items() if k not in ['input', 'output']}
        summary.append(item)
        (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(json.dumps(item), flush=True)
finally:
    store.flush()
    store.close()
