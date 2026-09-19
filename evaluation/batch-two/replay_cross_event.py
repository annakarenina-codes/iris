"""Opt-in live component-review replay against a saved article, not fresh search."""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'iris-backend'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Send the saved claim/article to configured OpenAI.')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required; this replay makes external provider calls')
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'iris-backend' / '.env')
    from pipeline.component_evidence import review_components
    from iris_trace.core import CURRENT, Store, Trace
    fixture = json.loads((ROOT / 'iris-backend/tests/fixtures/cross_event_shooting.json')
                         .read_text(encoding='utf-8'))
    started = time.monotonic()
    def run(claim, context):
        store = Store(Path(__file__).with_name('cross-event-traces.sqlite3'))
        trace = Trace(store, '/calibration/event-identity', {'text': claim}, True, True)
        token = CURRENT.set(trace)
        try:
            result = review_components(claim, [fixture['article']], context)
            trace.finish(result, 200 if result['status'] == 'ok' else 503)
            return result, trace.id
        finally:
            CURRENT.reset(token)
            store.flush()
            store.close()
    result, trace_id = run(fixture['claim'], fixture['source_context'])
    report = {
        'run_timestamp': datetime.now(timezone.utc).isoformat(),
        'basis_trace_id': fixture['trace_id'],
        'replay_trace_id': trace_id,
        'mode': 'Live OpenAI review; saved article; no fresh search, translation, extraction or HTTP endpoint run',
        'cache': 'bypassed (direct component review)',
        'cache_version': 'week7-event-identity-v13',
        'claim': fixture['claim'], 'article_url': fixture['article']['url'],
        'before': fixture['saved_review'], 'after': result,
        'seconds': round(time.monotonic() - started, 2),
        'passed': result.get('status') == 'ok' and result.get('verdict') == 'Not Found'
                  and not result.get('supporting_urls'),
    }
    # A labeled contrast: same identified incident, but an unsupported confession/motive.
    control_claim = (
        'The 31-year-old suspect who shot a 23-year-old livestream seller in Taytay on January 16 '
        'was arrested in Angono on January 17 and confessed to acting over online taunts.'
    )
    control, control_trace_id = run(control_claim, control_claim)
    report['positive_control'] = {
        'kind': 'Constructed same-incident partial-support control, not an original user request',
        'claim': control_claim, 'result': control,
        'trace_id': control_trace_id,
        'expected_verdict': 'Partially Verified',
        'passed': control.get('status') == 'ok' and control.get('verdict') == 'Partially Verified'
                  and control.get('supporting_urls') == [fixture['article']['url']],
    }
    report['passed'] = report['passed'] and report['positive_control']['passed']
    report['seconds'] = round(time.monotonic() - started, 2)
    output = Path(__file__).with_name('cross-event-live-result.json')
    if output.exists():
        archive = output.with_name('cross-event-live-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json')
        archive.write_bytes(output.read_bytes())
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'passed': report['passed'], 'seconds': report['seconds'],
                      'after_verdict': result.get('verdict'),
                      'after_sources': result.get('supporting_urls'),
                      'control_verdict': control.get('verdict'),
                      'control_status': control.get('status')}, ensure_ascii=True))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
