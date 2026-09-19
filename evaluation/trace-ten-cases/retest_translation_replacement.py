"""Fresh, translation-only live checks for the five previously failing posts."""

import hashlib
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
from iris_trace.core import CURRENT, Store, Trace
from pipeline.language_detector import detect_language
from pipeline.translator import translate_to_english, _numeric_literals, _timeout_seconds

OUT = HERE / 'translation-replacement-retest'
OUT.mkdir(exist_ok=False)
records = json.loads((HERE / 'observed_trace_records.json').read_text(encoding='utf-8'))
manifest = {
    'scope': 'Live translation only; no screening, extraction, search or verdict test.',
    'started_utc': datetime.now(timezone.utc).isoformat(),
    'provider': 'openai', 'model': os.getenv('IRIS_TRANSLATION_MODEL') or os.getenv('OPENAI_MODEL') or 'gpt-4o-mini',
    'timeout_seconds': _timeout_seconds(), 'retries': 0,
    'source_hashes': {name: hashlib.sha256((BACKEND / 'pipeline' / name).read_bytes()).hexdigest()
                      for name in ['translator.py', 'text_boundaries.py']},
}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
store = Store(OUT / 'traces.sqlite3')
summary = []
try:
    for record in records:
        number = record['case']
        if number not in [2, 5, 6, 8, 9]:
            continue
        original = record['input']['text']
        trace = Trace(store, '/calibration/translation', {'text': original, 'platform': 'harness'}, True, True)
        token = CURRENT.set(trace)
        print(f'START case {number}', flush=True)
        start = time.monotonic()
        try:
            language = detect_language(original)
            translated = translate_to_english(original, language)
            result = {'case': number, 'trace_id': trace.id, 'language': language,
                      'original_text': original, 'translated_text': translated,
                      'elapsed_seconds': round(time.monotonic() - start, 3),
                      'changed': translated != original,
                      'numeric_literals_preserved': _numeric_literals(original) == _numeric_literals(translated)}
            trace.finish(result)
        finally:
            CURRENT.reset(token)
        store.flush()
        (OUT / f'case-{number:02d}.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        compact = {key: value for key, value in result.items() if key not in ['original_text', 'translated_text']}
        summary.append(compact)
        (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(json.dumps(compact), flush=True)
finally:
    store.flush()
    store.close()
