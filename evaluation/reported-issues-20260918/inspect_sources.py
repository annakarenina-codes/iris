"""Fetch the five user-supplied public articles for extraction diagnostics."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'iris-backend'))
from pipeline.article_extractor import extract_article_text
import requests
from bs4 import BeautifulSoup

URLS = {
    'eala': 'https://www.abs-cbn.com/entertainment/showbiz/celebrities/2026/9/14/alex-eala-shares-front-row-with-anna-wintour-at-new-york-fashion-week-show-2307',
    'deped': 'https://www.gmanetwork.com/news/topstories/nation/1001536/are-k-12-grads-ready-for-work-adult-life-deped-eyes-longer-ojt/story/',
    'rene': 'https://www.abs-cbn.com/sports/basketball/2026/9/16/-para-kay-rene-ust-dedicates-uaap-season-89-campaign-to-baterbonia-family-2352',
    'moira': 'https://www.abs-cbn.com/entertainment/showbiz/music/2026/9/14/moira-dela-torre-hits-11-million-followers-on-spotify-1247',
    'vera': 'https://verafiles.org/articles/fact-check-romeo-poquiz-did-not-make-viral-statement-vs-marcoses',
}


if __name__ == '__main__':
    folder = Path(__file__).parent
    results = {}
    for name, url in URLS.items():
        result = extract_article_text(url)
        results[name] = result
        print(json.dumps({'case': name, 'status': result['status'],
                          'words': result['word_count'], 'method': result.get('extraction_method'),
                          'error': result.get('error')}), flush=True)
        try:
            response = requests.get(url, timeout=15, headers={'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/125.0 Safari/537.36'})
            response.raise_for_status()
            (folder / (name + '.html')).write_text(response.text, encoding='utf-8')
            soup = BeautifulSoup(response.text, 'html.parser')
            result['script_inventory'] = [{'type': tag.get('type'), 'id': tag.get('id'),
                                            'length': len(tag.get_text())}
                                           for tag in soup.find_all('script') if len(tag.get_text()) > 500]
        except requests.RequestException as exc:
            result['snapshot_error'] = type(exc).__name__
    (folder / 'source-baseline.json').write_text(json.dumps(results, indent=2, ensure_ascii=True), encoding='utf-8')
