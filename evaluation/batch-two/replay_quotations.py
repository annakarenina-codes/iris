"""Live screening/extraction only, with saved translations and no evidence search."""
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
    if not parser.parse_args().live:
        parser.error('--live is required to call the configured OpenAI services')
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'iris-backend/.env')
    from pipeline.content_profiler import profile_content
    from pipeline.claim_extractor import extract_claims
    from pipeline.quotation_context import comparable_utterance, speech_scopes, utterances
    from pipeline.text_boundaries import split_statement_segments
    from iris_trace.core import CURRENT, Store, Trace
    cases = json.loads((ROOT / 'iris-backend/tests/fixtures/quotation_cases.json').read_text(encoding='utf-8'))
    folder = Path(__file__).parent
    store = Store(folder / 'quotation-traces.sqlite3')
    output = {'timestamp': datetime.now(timezone.utc).isoformat(),
              'scope': 'Live OpenAI screening/extraction with saved translations; no fresh translation, search, evidence review or frontend run',
              'cache_version': 'week7-quotation-context-v14', 'cases': {}}
    try:
        for name, case in cases.items():
            trace = Trace(store, '/calibration/quotations', {'text': case['text']}, True, True)
            token = CURRENT.set(trace)
            try:
                profile = profile_content(case['text'], case['translated_text'])
                extracted = (extract_claims(profile['verification_text'], profile['normalized_verification_text'])
                             if profile['eligible_for_verification'] else None)
                if name == 'imagined':
                    checks = {'no_verification': not profile['eligible_for_verification'],
                              'all_three_questions_retained_as_excluded': len(profile['segments']) == 3
                              and all(s['speech_scope'] == 'imagined' for s in profile['segments'])}
                else:
                    claims = (extracted or {}).get('claims', [])
                    parts = split_statement_segments(case['translated_text'])
                    quotes = [q for s, scope in zip(parts, speech_scopes(parts)) if scope == 'reported'
                              for q in utterances(s)]
                    checks = {'completed_review': (extracted or {}).get('status') == 'ok',
                              'both_complete_utterances': len(quotes) == 2 and all(any(
                                  c['claim_type'] == 'attributed_statement'
                                  and 'padilla' in str((c.get('attribution') or {}).get('speaker', '')).lower()
                                  and comparable_utterance(q) in comparable_utterance(c['normalized_claim'])
                                  for c in claims) for q in quotes),
                              'bail_preserved': any('360,000' in c['normalized_claim'] for c in claims),
                              'impeachment_mechanism_preserved': any('mechanism' in c['normalized_claim'].lower() for c in claims)}
                record = {'basis_trace_id': case['trace_id'], 'trace_id': trace.id,
                          'profile': profile, 'extraction': extracted, 'checks': checks,
                          'passed': all(checks.values())}
                output['cases'][name] = record
                trace.finish(record, 200)
                print(json.dumps({'case': name, 'checks': checks, 'trace_id': trace.id,
                                  'claims': [c['normalized_claim'] for c in (extracted or {}).get('claims', [])]}, ensure_ascii=True), flush=True)
            finally:
                CURRENT.reset(token)
                store.flush()
    finally:
        store.close()
        target = folder / 'quotation-live-result.json'
        if target.exists():
            target.with_name('quotation-live-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json').write_bytes(target.read_bytes())
        target.write_text(json.dumps(output, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    return 0 if len(output['cases']) == 2 and all(c['passed'] for c in output['cases'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
