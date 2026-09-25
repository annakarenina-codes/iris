"""Replay saved attribution candidates; optional live final evidence review only."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'iris-backend'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    live = parser.parse_args().live
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'iris-backend/.env')
    import app
    from pipeline.attribution_integrity import ground_attribution
    from pipeline.claim_context import incident_anchor, incident_evidence_gate
    from pipeline.component_evidence import review_components
    from iris_trace.core import CURRENT, Store, Trace

    folder = Path(__file__).parent
    cases = json.loads((ROOT / 'iris-backend/tests/fixtures/attribution_cases.json').read_text(encoding='utf-8'))
    store = Store(folder / 'attribution-traces.sqlite3')
    output = {'timestamp': datetime.now(timezone.utc).isoformat(),
              'cache_version': app.RESULT_CACHE_VERSION,
              'scope': 'Saved extraction and articles; fresh attribution grounding/gates. '
                       + ('Live OpenAI final evidence review.' if live else 'No external calls.')
                       + ' No fresh translation, screening, claim extraction, search, URL fetch, or frontend test.',
              'cases': {}}
    try:
        for case in cases:
            trace = Trace(store, '/calibration/attribution', {'text': case['input_text']}, True, True)
            token = CURRENT.set(trace)
            try:
                claim = ground_attribution(case['claim'], case['input_text'])
                anchor = incident_anchor(claim['normalized_claim'], claim.get('evidence_context', ''))
                audits, eligible = [], []
                for article in case['articles']:
                    gate = app.attribution_evidence_gate(article, claim, anchors_only=True)
                    incident = incident_evidence_gate(article, anchor)
                    admitted = bool(app.compact_evidence_source(article) and article.get('text')
                                    and gate['matches'] and incident['matches'])
                    audits.append({'url': article['url'], 'admitted': admitted,
                                   'attribution': gate, 'incident': incident})
                    if admitted:
                        eligible.append(article)
                checks = {'assertion_unchanged': claim['normalized_claim'] == case['claim']['claim_text']}
                if case['name'] == 'diacritic':
                    checks['known_abs_cbn_article_admitted'] = any(
                        'palace-marcos-jr-won-t-interfere' in a['url'] for a in eligible)
                else:
                    checks['credit_removed'] = claim['attribution']['source'] is None
                    checks['speaker_retained'] = claim['attribution']['speaker'] == 'Melvin Matibag'
                    checks['unnamed_speaker_article_rejected'] = not any(
                        'ginang-nasawi' in a['url'] for a in eligible)
                review = (review_components(claim['normalized_claim'], eligible,
                                            source_context=claim.get('evidence_context', '')) if eligible else
                          {'status': 'no_evidence', 'verdict': 'Not Found', 'supporting_urls': []}) if live else None
                if live:
                    checks['review_completed'] = review['status'] in {'ok', 'no_evidence'}
                    if case['name'] == 'diacritic':
                        checks['known_article_supplies_reviewed_support'] = (
                            review.get('verdict') in {'Verified', 'Partially Verified'} and any(
                                'palace-marcos-jr-won-t-interfere' in url
                                for url in review.get('supporting_urls', [])))
                    else:
                        # Saved Matibag articles concern other investigations, not this death.
                        checks['unrelated_investigations_not_used_as_support'] = (
                            review.get('verdict') == 'Not Found' and not review.get('supporting_urls'))
                record = {'basis_trace_id': case['trace_id'], 'trace_id': trace.id,
                          'claim': claim, 'candidate_audit': audits, 'admitted_count': len(eligible),
                          'review': review, 'checks': checks, 'passed': all(checks.values())}
                output['cases'][case['name']] = record
                trace.finish(record, 200 if not review or review['status'] in {'ok', 'no_evidence'} else 503)
                print(json.dumps({'case': case['name'], 'checks': checks, 'eligible': len(eligible),
                                  'verdict': (review or {}).get('verdict'), 'trace_id': trace.id}), flush=True)
            finally:
                CURRENT.reset(token)
                store.flush()
    finally:
        store.close()
        target = folder / ('attribution-live-result.json' if live else 'attribution-replay-result.json')
        if target.exists():
            target.with_name(target.stem + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json').write_bytes(target.read_bytes())
        target.write_text(json.dumps(output, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    return 0 if len(output['cases']) == 2 and all(c['passed'] for c in output['cases'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
