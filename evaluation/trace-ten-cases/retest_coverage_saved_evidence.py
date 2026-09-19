"""Fresh extraction and evidence review of saved articles, without new search."""

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
from pipeline.claim_extractor import extract_claims, DEFAULT_CLAIM_REVIEW_MODEL
from pipeline.component_evidence import review_components
from iris_trace.core import CURRENT, Store, Trace

parser = argparse.ArgumentParser()
parser.add_argument('--output-name', default='coverage-entailment-replay')
args = parser.parse_args()
if not args.output_name or Path(args.output_name).name != args.output_name or args.output_name in {'.', '..'}:
    parser.error('output-name must be a directory name, not a path')
OUT = HERE / args.output_name
OUT.mkdir(exist_ok=False)
BASELINE = HERE / 'component-review-retest'
manifest = {
    'started_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Fresh OpenAI extraction of saved profiler text; targeted review of saved retrieved articles. NO new search, NO full endpoint retest.',
    'reason': 'Isolated extraction and passage-matching check. See the separate live runs for current retrieval status.',
    'model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
    'coverage_review_model': DEFAULT_CLAIM_REVIEW_MODEL,
    'entailment_review_model': os.getenv('IRIS_EVIDENCE_REVIEW_MODEL', 'gpt-4.1-2025-04-14'),
    'code_sha256': {name: hashlib.sha256((BACKEND / name).read_bytes()).hexdigest()
                   for name in ['pipeline/claim_extractor.py', 'pipeline/claim_coverage.py',
                                'pipeline/component_evidence.py']},
}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
store = Store(OUT / 'traces.sqlite3')
db = sqlite3.connect(f'file:{(BASELINE / "traces.sqlite3").as_posix()}?mode=ro', uri=True)

try:
    for number in [3, 7]:
        saved = json.loads((BASELINE / f'case-{number:02}.json').read_text(encoding='utf-8'))
        original = saved['input']['text']
        profile = saved['output']['debug']['content_profile']
        source = profile['normalized_verification_text']
        rows = db.execute('SELECT data FROM artifacts WHERE trace_id=?', (saved['trace_id'],)).fetchall()
        articles = {}
        for row in rows:
            artifact = json.loads(row[0])
            if artifact['stage_id'] == 'retrieval.article_extract':
                article = artifact['output']
                if isinstance(article, dict) and article.get('status') == 'extracted' and article.get('text'):
                    articles[article['url']] = article
        trace = Trace(store, '/calibration/replay', {'text': original}, True, True)
        token = CURRENT.set(trace)
        print(f'START replay case {number}: {trace.id}', flush=True)
        try:
            extraction = extract_claims(source)
            if number == 3:
                probe_claim = next(c['normalized_claim'] for c in saved['output']['claims']
                                   if 'suspects remain' in c['normalized_claim'])
                selected = [a for url, a in articles.items() if 'yulo-ambush' in url]
                expected = 'Not Found: the saved Yulo article concerns a different incident.'
            else:
                probe_claim = original
                selected = [a for url, a in articles.items() if
                            'padilla-tests-auditor' in url or 'padilla-vp-secret-funds-used-vs-reds' in url]
                expected = 'Inspect full versus partial support; background and the stated medicines/funds rationale need particular scrutiny.'
            if not selected:
                raise ValueError('required_saved_evidence_missing')
            reviewed = review_components(probe_claim, selected, source_context=original)
            result = {'case': number, 'trace_id': trace.id, 'mode': 'targeted_saved_evidence_replay',
                      'baseline_trace_id': saved['trace_id'], 'extraction': extraction,
                      'probe': {'claim': probe_claim, 'expected_review': expected,
                                'saved_articles': selected, 'review': reviewed}}
            (OUT / f'case-{number:02}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            trace.finish(result, 200)
            print(json.dumps({'case': number, 'extraction_status': extraction['status'],
                              'claim_count': len(extraction['claims']), 'review_status': reviewed['status'],
                              'verdict': reviewed['verdict']}), flush=True)
        except Exception as error:
            trace.finish({'error': type(error).__name__}, 500, error)
            raise
        finally:
            CURRENT.reset(token)
            store.flush()
finally:
    db.close()
    store.close()
