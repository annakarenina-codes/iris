"""Bounded live provider probes. Never records credentials or request URLs."""

import importlib.metadata
import json
import sys
from pathlib import Path
from unittest.mock import patch

import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'iris-backend'))
from pipeline.translator import sanitize_translation

records = json.loads((HERE / 'observed_trace_records.json').read_text(encoding='utf-8'))
peso = next(r['input']['text'] for r in records if r['case'] == 9)
original_get = requests.get
report = {'library': importlib.metadata.version('deep-translator'), 'probes': []}
for label, source, text in [('short_auto', 'auto', 'Magandang umaga.'),
                            ('peso_auto', 'auto', peso), ('peso_explicit', 'tl', peso)]:
    probe = {'label': label, 'source': source, 'requests': []}

    def bounded_get(*args, **kwargs):
        kwargs['timeout'] = (5, 15)
        response = original_get(*args, **kwargs)
        soup = BeautifulSoup(response.text, 'html.parser')
        candidate = soup.select_one('div.t0, div.result-container')
        probe['requests'].append({
            'status': response.status_code,
            'content_type': response.headers.get('Content-Type'),
            'page_title': soup.title.get_text() if soup.title else None,
            'candidate_found': candidate is not None,
            'candidate_is_service_error': bool(candidate and
                sanitize_translation(text, candidate.get_text(strip=True)) == text
                and candidate.get_text(strip=True) != text),
        })
        return response

    try:
        with patch('deep_translator.google.requests.get', side_effect=bounded_get):
            result = GoogleTranslator(source=source, target='english').translate(text)
        probe.update(output=result, accepted=sanitize_translation(text, result) != text)
    except Exception as error:
        probe['error_type'] = type(error).__name__
    report['probes'].append(probe)
    print(json.dumps(probe, ensure_ascii=True), flush=True)
(HERE / 'translation-provider-diagnosis.json').write_text(
    json.dumps(report, ensure_ascii=True, indent=2), encoding='utf-8')
