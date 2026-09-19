"""Preserve selected TRACE evidence read-only and inventory the audit cases."""
import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BACKEND = ROOT / 'iris-backend'
SECOND = [
    '43ffed6000b44606957e33c1fb6897c4', '65c9640cd64746d4bbb23a8a8ef678de',
    'adcb8b846fe14973b948e2385889b596', 'a68d967158d1463c9c7fcfe1e7906b8c',
    '11530398d3ef40c6815f036fabd93f80', '7bb61e21b74f47068bc6e43228fcaf8c',
    '40484e95fd85427288f7e01abc5550a4', 'fc9b9a267e944e83a74cd5fe3d868c2c',
    'e510dea09852408da0d385dcdbe6d3a2', '0bca685524f44da4ac4cf6eacc989046',
    'f974412e5d344e88a705874315f4d2fe', 'c9baafbe081546e2b6912a6f65d56b43',
    'e896ffdbe66c4fd8bb99fe58373960fe', '4ef5f9af349944858d36e449df69ac5b',
    '16e45425882848a48c4d0c5487e479d9', '79740d5ef657430d857e9ada9e01590f']


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def capture(db, trace_id):
    row = db.execute('SELECT * FROM traces WHERE id=?', (trace_id,)).fetchone()
    if row is None:
        return {'trace_id': trace_id, 'missing': True}
    trace = dict(row)
    trace['summary'] = json.loads(trace['summary'] or '{}')
    events = [json.loads(r[0]) for r in db.execute(
        'SELECT data FROM events WHERE trace_id=? ORDER BY seq', (trace_id,))]
    artifacts = []
    for art in db.execute('SELECT kind,sha256,data FROM artifacts WHERE trace_id=?', (trace_id,)):
        try:
            value = json.loads(art['data'])
        except (ValueError, UnicodeError):
            continue
        artifacts.append({'kind': art['kind'], 'sha256': art['sha256'], 'value': value})
    return {'trace': trace, 'events': events, 'artifacts': artifacts}


def main():
    snapshots = HERE / 'historical'
    snapshots.mkdir(exist_ok=True)
    first = read(ROOT / 'evaluation/trace-ten-cases/observed_trace_records.json')
    cases = []
    for record in first:
        ident = f'A{record["case"]:02d}'
        text = record['input']['text']
        write(snapshots / f'{ident}.json', record)
        cases.append({'id': ident, 'batch': 'Original ten', 'text': text,
                      'historical_trace': record['trace']['id'],
                      'historical_file': f'historical/{ident}.json'})
    source = BACKEND / '.iris-trace/traces.sqlite3'
    with sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        inventory = [dict(r) for r in db.execute(
            'SELECT id,created,status,title,capture_status FROM traces ORDER BY created DESC')]
        write(HERE / 'available-traces.json', inventory)
        for i, trace_id in enumerate(SECOND, 1):
            ident = f'B{i:02d}'
            record = capture(db, trace_id)
            inputs = [a['value'] for a in record.get('artifacts', []) if a['kind'] == 'request_input']
            if not inputs or not isinstance(inputs[0].get('text'), str):
                raise ValueError(f'Missing full input for {ident}: {trace_id}')
            write(snapshots / f'{ident}.json', record)
            cases.append({'id': ident, 'batch': 'Second batch', 'text': inputs[0]['text'],
                          'historical_trace': trace_id, 'historical_file': f'historical/{ident}.json'})
    recent = read(ROOT / 'evaluation/reported-issues-20260918/cases.json')
    for i, (name, text) in enumerate(recent.items(), 1):
        cases.append({'id': f'C{i:02d}', 'batch': 'September 18 reports', 'name': name, 'text': text,
                      'historical_file': 'evaluation/reported-issues-20260918/diagnosis.md'})
    for case in cases:
        case['input_sha256'] = hashlib.sha256(case['text'].encode()).hexdigest()
        case['evaluation_role'] = 'development: previously examined, not held out'
    write(HERE / 'cases.json', cases)
    paths = [BACKEND / 'app.py', BACKEND / 'requirements.txt'] + sorted((BACKEND / 'pipeline').glob('*.py')) + sorted((BACKEND / 'iris_trace').glob('*.py'))
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'case_count': len(cases),
                'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'production_hashes': hashes, 'historical_database': str(source),
                'latest_historical_utc': datetime.fromtimestamp(inventory[0]['created'], timezone.utc).isoformat(),
                'notes': ['Source database read-only; production behavior not modified.',
                          'No .env or API credentials copied.', 'Historical runs have different versions and partial captures.',
                          'Additional new blind cases not yet located; no existing case is a held-out test.']}
    write(HERE / 'baseline-manifest.json', manifest)
    print(json.dumps({k: manifest[k] for k in ['case_count', 'latest_historical_utc']}, indent=2))
    for case in cases:
        print(case['id'], case.get('name', ''), case['text'][:135].encode('ascii', errors='backslashreplace').decode())


if __name__ == '__main__':
    main()
