"""Bounded diagnostic queries for two known missing articles, not verdicts."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'iris-backend'))
from pipeline.sources import get_all_sources
from pipeline.search import brave_search

sources = {s['name']: s for s in get_all_sources()}
results = []
for source, query in [('VERA Files', '"Romeo Poquiz"'),
                      ('VERA Files', 'Romeo Poquiz viral statement Marcos'),
                      ('GMA News', 'DepEd OJT 640 80 160 hours'),
                      ('GMA News', 'Sonny Angara senior high school OJT hours')]:
    result = brave_search(query, sources[source], count=10)
    results.append(result)
    print(json.dumps({'query': query, 'status': result['status'],
                      'urls': [r['url'] for r in result['results']]}), flush=True)
(Path(__file__).parent / 'search-probes.json').write_text(json.dumps(results, indent=2, ensure_ascii=True), encoding='utf-8')
