"""Reference download and saved-evidence controls, never automatic retrieval credit."""
import json
import argparse
import logging
import sys
from datetime import datetime, timezone

from collect import HERE, ROOT, read, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download-only', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / 'iris-backend'))
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'iris-backend/.env')
    from pipeline.article_extractor import extract_article_text
    from pipeline.component_evidence import review_components
    from iris_trace.core import Store, Trace, CURRENT
    folder = HERE / 'reference-controls'
    folder.mkdir(exist_ok=True)
    logging.basicConfig(filename=folder / 'services.log', level=logging.INFO, force=True)
    refs = {}
    for filename in ['reference-access.json', 'additional-references.json']:
        for key, record in read(ROOT / 'evaluation/trace-ten-cases/retest-20260912' / filename).items():
            if isinstance(record, dict) and record.get('url'):
                refs[key] = {'url': record['url'], 'prior_inspection': record.get('checked_utc')}
    for name, value in read(ROOT / 'evaluation/reported-issues-20260918/source-reextract.json').items():
        refs['R-' + name] = {'url': value['url']}
    refs['R-fanmeet'] = {'url': 'https://www.abs-cbn.com/entertainment/showbiz/events/2026/6/9/byeon-woo-seok-returning-to-ph-for-october-fan-meet-1729'}
    cases = {c['id']: c for c in read(HERE / 'cases.json')}
    store = Store(folder / 'traces.sqlite3')
    try:
        for key, reference in refs.items():
            target = folder / (key + '.json')
            if target.exists():
                continue
            result = extract_article_text(reference['url'])
            write(target, {**reference, 'checked_utc': datetime.now(timezone.utc).isoformat(), 'extraction': result,
                           'scope': 'Known URL supplied to extractor; NOT a search result or retrieval success.'})
            print(json.dumps({'reference': key, 'status': result.get('status'),
                              'words': result.get('word_count'), 'error': result.get('error')}), flush=True)
        if args.download_only:
            return
        for case_id, key in [('A07', 'S01'), ('B15', 'R-fanmeet'), ('C04', 'R-deped'),
                             ('C07', 'R-moira'), ('C08', 'R-vera')]:
            target = folder / (case_id + '-review.json')
            if target.exists():
                continue
            reference = read(folder / (key + '.json'))['extraction']
            if reference.get('status') != 'extracted' or not reference.get('text'):
                write(target, {'case_id': case_id, 'status': 'not_run', 'reason': 'reference_extraction_failed'})
                continue
            text = cases[case_id]['text']
            trace = Trace(store, '/audit/reference-control', {'text': text}, True, True)
            token = CURRENT.set(trace)
            try:
                review = review_components(text, [reference], source_context=text)
                result = {'case_id': case_id, 'reference': key, 'trace_id': trace.id, 'review': review,
                          'scope': 'Fresh model review with known article supplied. Does not test search or claim extraction.'}
                trace.finish(result, 503 if review.get('status') == 'error' else 200)
                write(target, result)
                print(json.dumps({'case': case_id, 'control_verdict': review.get('verdict'),
                                  'status': review.get('status')}), flush=True)
            finally:
                CURRENT.reset(token)
                store.flush()
    finally:
        store.close()


if __name__ == '__main__':
    main()
