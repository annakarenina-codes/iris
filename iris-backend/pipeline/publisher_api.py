"""
Reads an article through the publisher's own public content API.

VERA Files put its pages behind a challenge page that answers automated requests
with "Verifying if your connection is secure" and HTTP 429, so IRIS could no
longer download the fact-checks it relies on most (saved case C08). The same site
publishes every article through its public WordPress API, which is the channel it
offers to programs rather than browsers, so IRIS reads the article there instead.
Only approved sources that declare a content API are read this way, and the API
must return the same article address that IRIS asked for.
"""

from __future__ import annotations

from iris_trace.core import traced, event

import re
import time
from html import unescape
from typing import Dict, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover - depends on local environment setup
    requests = None

from pipeline.article_extractor import (MIN_METADATA_WORDS, THIN_ARTICLE_WORDS, cached_article,
                                        normalize_article_url, remember_article)
from pipeline.evidence_urls import article_url_rejection
from pipeline.sources import get_source_by_name

REQUEST_TIMEOUT_SECONDS = 10
MAX_SEARCH_RESULTS = 5
FIELDS = 'link,title,content,date,categories'
CATEGORY_CACHE_SECONDS = 3600
# VERA Files files its columns under these, and its fact-checks under FACT CHECK.
OPINION_CATEGORIES = {'commentary', 'first person', "chit's desk", "bullit's eye", 'reviews'}
_categories = {}


def content_api(source_name: str) -> Optional[str]:
    """The article API this source publishes, when it declares one."""
    source = get_source_by_name(source_name)
    return (source or {}).get('content_api')


def category_names(api: str, ids) -> List[str]:
    """Names of a post's categories, so a column can be told from a report."""
    if not ids:
        return []
    cached = _categories.get(api)
    if not cached or time.time() - float(cached['fetched']) >= CATEGORY_CACHE_SECONDS:
        try:
            response = requests.get(api.rsplit('/', 1)[0] + '/categories', params={'per_page': 100},
                                    timeout=REQUEST_TIMEOUT_SECONDS,
                                    headers={'User-Agent': 'Mozilla/5.0 (compatible; IRIS fact-check reader)',
                                             'Accept': 'application/json'})
            response.raise_for_status()
            names = {int(item['id']): unescape(str(item.get('name') or '')) for item in response.json()}
        except Exception as error:  # pragma: no cover - a naming failure must not block evidence
            event('retrieval.publisher_categories_unavailable', error=type(error).__name__)
            return []
        cached = {'fetched': time.time(), 'names': names}
        _categories[api] = cached
    return [cached['names'][i] for i in ids if i in cached['names']]


def _text(html: str) -> str:
    without_markup = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', str(html or ''), flags=re.S | re.I)
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', without_markup))).strip()


def _slug(url: str) -> str:
    return url.rstrip('/').rsplit('/', 1)[-1].split('?')[0]


def _same_article(candidate: str, wanted: str) -> bool:
    return normalize_article_url(str(candidate or '')).rstrip('/') == wanted.rstrip('/')


def _ask(api: str, params: Dict[str, object]) -> List[Dict[str, object]]:
    response = requests.get(api, params={**params, '_fields': FIELDS},
                            timeout=REQUEST_TIMEOUT_SECONDS,
                            headers={'User-Agent': 'Mozilla/5.0 (compatible; IRIS fact-check reader)',
                                     'Accept': 'application/json'})
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


@traced('retrieval.publisher_api', dependency=True)
def article_from_api(url: str, source_name: str) -> Optional[Dict[str, object]]:
    """The article's own text from the publisher's API, or None when it cannot be read there."""
    api = content_api(source_name)
    normalized_url = normalize_article_url(url)
    if not api or requests is None or article_url_rejection(normalized_url, source_name):
        return None

    reused = cached_article(normalized_url)
    if reused is not None:
        return reused

    slug = _slug(normalized_url)
    try:
        posts = _ask(api, {'slug': slug, 'per_page': 3})
        if not any(_same_article(post.get('link'), normalized_url) for post in posts):
            # The address slug and the stored slug differ on some articles; ask by its words.
            posts = _ask(api, {'search': slug.replace('-', ' '), 'per_page': MAX_SEARCH_RESULTS})
    except Exception as error:  # pragma: no cover - network failure must never break a check
        event('retrieval.publisher_api_unavailable', url=normalized_url, error=type(error).__name__)
        return None

    for post in posts:
        if not _same_article(post.get('link'), normalized_url):
            continue
        text = _text(post.get('content', {}).get('rendered', ''))
        words = len(re.findall(r'\b\w+\b', text))
        if words < MIN_METADATA_WORDS:
            continue
        sections = category_names(api, post.get('categories') or [])
        return remember_article(normalized_url, {
            'url': normalized_url,
            'status': 'extracted',
            'error': None,
            'sections': sections,
            'is_opinion': any(name.casefold() in OPINION_CATEGORIES for name in sections),
            'title': _text(post.get('title', {}).get('rendered', '')) or None,
            'description': '',
            'text': text,
            'word_count': words,
            'published_at': post.get('date'),
            'extraction_method': 'publisher_api',
            'extraction_quality': 'full' if words >= THIN_ARTICLE_WORDS else 'thin',
        })

    event('retrieval.publisher_api_missing', url=normalized_url, returned=len(posts))
    return None
