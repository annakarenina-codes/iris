"""Compare extraction against downloaded pages without further network calls."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'iris-backend'))
from pipeline import article_extractor as module
from inspect_sources import URLS

folder = Path(__file__).parent
results = {}
for name, url in URLS.items():
    response = SimpleNamespace(text=(folder / (name + '.html')).read_text(encoding='utf-8'),
                               url=url, raise_for_status=lambda: None)
    with patch.object(module.requests, 'get', return_value=response), \
         patch.object(module, '_trafilatura_text', return_value=''):
        result = module.extract_article_text(url)
    results[name] = result
    print(json.dumps({'case': name, 'words': result['word_count'], 'method': result.get('extraction_method')}))
(folder / 'source-reextract.json').write_text(json.dumps(results, indent=2, ensure_ascii=True), encoding='utf-8')
