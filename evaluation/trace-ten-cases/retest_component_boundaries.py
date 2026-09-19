"""Bounded live review of saved passages; no search or extraction rerun."""

import hashlib
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / 'iris-backend'
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(BACKEND)
from dotenv import load_dotenv
load_dotenv(BACKEND / '.env')
from pipeline.component_evidence import review_components
from pipeline.claim_context import incident_anchor, incident_evidence_gate
from iris_trace.core import CURRENT, Store, Trace

parser = argparse.ArgumentParser()
parser.add_argument('--output-name', default='coverage-entailment-v11-boundaries')
parser.add_argument('--probe', choices=['investigation', 'wrong-incident', 'testimony-year', 'padilla-wamil'])
args = parser.parse_args()
if not args.output_name or Path(args.output_name).name != args.output_name or args.output_name in {'.', '..'}:
    parser.error('output-name must be a directory name, not a path')
OUT = HERE / args.output_name
OUT.mkdir(exist_ok=False)
BASE = HERE / 'coverage-entailment-v10-live'
saved3 = json.loads((BASE / 'case-03.json').read_text(encoding='utf-8'))
saved7 = json.loads((BASE / 'case-07.json').read_text(encoding='utf-8'))

def captured(folder, trace_id):
    with sqlite3.connect(f'file:{(folder / "traces.sqlite3").as_posix()}?mode=ro', uri=True) as db:
        return [json.loads(r[0]) for r in db.execute('SELECT data FROM artifacts WHERE trace_id=?', (trace_id,))]


def articles(rows):
    return list({x['output']['url']: x['output'] for x in rows
                 if x['stage_id'] == 'retrieval.article_extract'
                 and isinstance(x.get('output'), dict)
                 and x['output'].get('status') == 'extracted' and x['output'].get('text')}.values())


rows3 = captured(BASE, saved3['trace_id'])
pool3 = articles(rows3)
pool7 = articles(captured(BASE, saved7['trace_id']))
inventory = next(x['output']['claims'] for x in rows3 if x['stage_id'] == 'claims.extract')
investigation = next(c['claim_text'] for c in inventory if 'suspects remain' in c['claim_text'])
testimony = next(c['claim_text'] for c in inventory if 'oral testimony' in c['claim_text'])
baseline = HERE / 'component-review-retest'
baseline3 = json.loads((baseline / 'case-03.json').read_text(encoding='utf-8'))
wrong_articles = [a for a in articles(captured(baseline, baseline3['trace_id'])) if 'yulo-ambush' in a['url']]
probes = [
    ('investigation', investigation, saved3['input']['text'],
     [a for a in pool3 if 'cctv' in a['text'].lower() and 'carpenter' in a['text'].lower()]),
    ('wrong-incident', investigation, saved3['input']['text'], wrong_articles),
    ('testimony-year', testimony, saved3['input']['text'],
     [a for a in pool3 if 'delivered oral testimonies' in a['text'].lower() and '2016' in a['text']]),
    ('padilla-wamil', saved7['input']['text'], saved7['input']['text'],
     [a for a in pool7 if 'padilla-tests-auditor' in a['url'] or 'padilla-vp-secret-funds-used-vs-reds' in a['url']]),
]
if any(not p[3] for p in probes):
    raise ValueError('required_saved_probe_articles_missing')
if args.probe:
    probes = [p for p in probes if p[0] == args.probe]
manifest = {
    'started_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Fresh OpenAI component reviews of saved articles only. NO fresh search, extraction or full endpoint run.',
    'model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
    'review_model': os.getenv('IRIS_EVIDENCE_REVIEW_MODEL', 'gpt-4.1-2025-04-14'),
    'code_sha256': {name: hashlib.sha256((BACKEND / name).read_bytes()).hexdigest()
                   for name in ['app.py', 'pipeline/component_evidence.py', 'pipeline/claim_context.py']},
}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
store = Store(OUT / 'traces.sqlite3')
summary = []
try:
    for name, claim, context, selected in probes:
        trace = Trace(store, '/calibration/components', {'text': claim}, True, True)
        token = CURRENT.set(trace)
        print(f'START {name}: {trace.id}', flush=True)
        try:
            anchor = incident_anchor(claim, context)
            gate = [{'url': a['url'], **incident_evidence_gate(a, anchor)} for a in selected]
            # Review even rejected candidates here to test the model independently
            # of the production gate, which would exclude a wrong-incident article.
            result = review_components(claim, selected, source_context=context)
            output = {'probe': name, 'trace_id': trace.id, 'claim': claim,
                      'incident_gate': gate, 'saved_articles': selected, 'review': result}
            (OUT / f'{name}.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
            trace.finish(output, 200 if result['status'] == 'ok' else 503)
            item = {'probe': name, 'trace_id': trace.id, 'status': result['status'],
                    'verdict': result['verdict'], 'components': [p['component'] for p in result['components']]}
            summary.append(item)
            (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(item, ensure_ascii=True), flush=True)
        finally:
            CURRENT.reset(token)
            store.flush()
finally:
    store.close()
