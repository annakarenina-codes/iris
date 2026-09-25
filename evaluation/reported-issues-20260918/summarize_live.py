"""Read saved retests without repeating paid API calls."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for label in ['rate-diagnosis', 'repaired-v16', 'bounded-retry']:
    folder = ROOT / label
    for path in sorted(folder.glob('*.json')):
        run = json.loads(path.read_text(encoding='utf-8'))
        body = run['response']
        print(json.dumps({'run': label, 'case': run['case'], 'http': run['http_status'],
                          'seconds': run['seconds'], 'trace': run.get('headers'),
                          'error': body.get('reason_code'),
                          'claims': [{'text': c['claim_text'], 'verdict': c.get('verdict'),
                                      'sources': [s['url'] for s in c.get('evidence_sources', [])]}
                                     for c in body.get('claims', [])]}, ensure_ascii=True))
    db = folder / 'traces.sqlite3'
    if not db.exists():
        continue
    with sqlite3.connect(f'{db.as_uri()}?mode=ro', uri=True) as connection:
        for trace_id, data in connection.execute('SELECT trace_id, data FROM events ORDER BY trace_id, seq'):
            record = json.loads(data)
            if 'component.rate_limit' in data:
                print('RATE_LIMIT', label, trace_id, json.dumps(record, ensure_ascii=True))
