"""Offline, narrow acceptance checks. Never substitute these for evidence review."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent
POSITIVE = {'Verified', 'Partially Verified'}
PASSING = {'A01','A04','A10','B02','B03','B06','B09','B10','B11','B13','B14','C01','C05'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def normalized(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value).lower()).strip()


def check_output(ident, run, expected_hash):
    checks = []
    def add(name, status, reason):
        checks.append({'check': name, 'status': status, 'reason': reason})
    if not isinstance(run, dict) or run.get('case_id') != ident or run.get('input_sha256') != expected_hash:
        add('capture_integrity', 'FAIL', 'Wrong case, missing input hash, or different input; cannot compare.')
        return checks
    body = run.get('response')
    if not isinstance(body, dict):
        add('capture_integrity', 'FAIL', 'Missing structured response.')
        return checks
    claims = body.get('claims', [])
    if not isinstance(claims, list) or any(not isinstance(c, dict) for c in claims):
        add('capture_integrity', 'FAIL', 'Malformed claims collection.')
        return checks
    add('capture_integrity', 'PASS', 'Case ID, exact input hash and response shape match.')
    technical = run.get('http_status') != 200 or body.get('status') == 'processing_error'
    if technical:
        no_verdict = body.get('verdict') is None and not body.get('evidence_sources') and not any(c.get('verdict') in POSITIVE for c in claims)
        explicit = bool(body.get('reason_code') and body.get('message'))
        add('technical_error_is_not_verdict', 'PASS' if no_verdict and explicit else 'FAIL',
            'A failed review must explain the error and issue no factual verdict.')
        add('request_completion', 'FAIL', f"Request did not complete: {body.get('reason_code', run.get('http_status'))}.")
        return checks
    add('request_completion', 'PASS', 'HTTP 200; completion alone is not accuracy.')
    components = [(c, p) for c in claims for p in (c.get('component_review') or {}).get('components', [])]
    if ident == 'B05':
        bad = [p for _, p in components if normalized(p.get('component')) in {'arrested', 'and was arrested', 'was arrested'} and p.get('status') == 'supported']
        add('no_detached_arrest_credit', 'FAIL' if bad else 'PASS' if components else 'NEEDS_REVIEW',
            'An isolated arrest must not earn credit. A complete assertion still requires event-identity review.')
    if ident == 'B12':
        bad = [p for _, p in components if normalized(p.get('component')) == 'causes']
        add('no_detached_causes', 'FAIL' if bad else 'PASS' if components else 'NEEDS_REVIEW',
            'The trailing word causes must remain with its environmental-advocacy assertion.')
    targets = {
        'C02': ('dict', 'zuckerberg'),
        'C03': ('wintour', 'us open'),
        'B15': ('secret library', 'october 10'),
    }
    if ident in targets:
        terms = targets[ident]
        matches = [c for c in claims if all(t in normalized(c.get('claim_text')) for t in terms)]
        if not matches:
            add('known_supported_assertion', 'NEEDS_REVIEW', 'Expected assertion not found by the selector; inspect omission or changed decomposition.')
        else:
            add('known_supported_assertion', 'PASS' if all(c.get('verdict') == 'Verified' for c in matches) else 'FAIL',
                'The saved reference supports this assertion. A new evidence pool must be inspected before attributing a failure to matching.')
    if ident == 'C06':
        named = [c for c in claims if 'padilla' in normalized(c.get('claim_text')) and c.get('claim_type') == 'attributed_statement']
        add('named_speaker_retained', 'PASS' if named and all((c.get('attribution') or {}).get('speaker') for c in named) else 'FAIL',
            'The explicitly named Padilla speaker must not become null; identity correctness remains a review check.')
    if ident in {'B07', 'B16'}:
        add('routing_does_not_verify', 'FAIL' if claims else 'PASS',
            'This advocacy/out-of-scope fixture must not be sent through factual verification. Also inspect the user-facing explanation.')
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', type=Path, default=AUDIT / 'current-baseline')
    parser.add_argument('--output-dir', type=Path, default=HERE / 'baseline-check')
    args = parser.parse_args()
    cases = read(AUDIT / 'cases.json')
    expected = {r['id']: r for r in read(AUDIT / 'expectations.json')}
    notes = read(AUDIT / 'review_notes.json')
    rows = []
    for case in cases:
        ident = case['id']
        assert hashlib.sha256(case['text'].encode()).hexdigest() == case['input_sha256']
        path = args.results_dir / f'{ident}.json'
        checks = check_output(ident, read(path), case['input_sha256']) if path.exists() else [
            {'check': 'capture_present', 'status': 'NEEDS_REVIEW', 'reason': 'No saved run supplied.'}]
        if ident in PASSING and path.exists():
            old = read(AUDIT / 'current-baseline' / path.name)['response']
            new = read(path).get('response') or {}
            signature = lambda b: [c.get('verdict') for c in b.get('claims', [])] or [b.get('verdict')]
            checks.append({'check': 'passing_baseline_signature',
                           'status': 'PASS' if signature(old) == signature(new) else 'NEEDS_REVIEW',
                           'reason': 'Count/verdict signature only; unchanged labels do not prove unchanged meaning or citations.'})
        rows.append({'id': ident, 'topic': expected[ident]['topic'], 'input_sha256': case['input_sha256'],
                     'expected_behavior': expected[ident]['expected_behavior'],
                     'prior_manual_assessment': notes[ident]['result'],
                     'checks': checks, 'semantic_review': 'REQUIRED for new runs',
                     'reference_ids': expected[ident]['reference_ids']})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter(c['status'] for r in rows for c in r['checks'])
    payload = {'results_directory': str(args.results_dir.resolve()), 'case_count': len(rows),
               'check_counts': dict(counts), 'scope': 'Offline output checks only. No services or backend executed. Not accuracy scores.', 'cases': rows}
    (args.output_dir / 'checks.json').write_text(json.dumps(payload, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    lines = ['# Regression Check Results', '', payload['scope'], '',
             f"Cases: {len(rows)}. Check results: {dict(counts)}. Counts are checks, not cases.", '',
             '| Case | Prior manual assessment | Automated failures / review flags | Full evidence review |', '|---|---|---|---|']
    for r in rows:
        flags = '; '.join(c['check'] + ': ' + c['status'] for c in r['checks'] if c['status'] != 'PASS')
        lines.append(f"| {r['id']} | {r['prior_manual_assessment']} | {flags or 'No narrow check failed; not a case pass'} | Required for a new run |")
    (args.output_dir / 'RESULTS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'cases': len(rows), 'checks': dict(counts), 'report': str(args.output_dir / 'RESULTS.md')}))
    return 1 if counts['FAIL'] else 2 if counts['NEEDS_REVIEW'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
