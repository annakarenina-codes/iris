"""
Finds fact-checks through a publisher's own sitemap when web search misses them.

Saved case C08: VERA Files had published "Romeo Poquiz did not make viral statement vs
Marcoses", but the search provider never returned it, even for its exact headline with a
site filter. The sitemap a publisher offers lists its articles, so IRIS can look up recent
fact-checks there directly. Only approved sources with a declared sitemap are used, and the
articles are read through the normal extraction path.
"""

from __future__ import annotations

from iris_trace.core import traced, event

import re
import time
from typing import Dict, List, Optional
from urllib.parse import urlsplit

try:
    import requests
except ImportError:  # pragma: no cover - depends on local environment setup
    requests = None

from pipeline.evidence_urls import article_url_rejection, clean_article_url
from pipeline.sources import get_fact_check_sources

REQUEST_TIMEOUT_SECONDS = 10
RECENT_SITEMAP_PAGES = 2          # newest pages only: recent fact-checks, not the whole archive
ARTICLE_SITEMAP = re.compile(r'/(?:post|article|news)-sitemap\d*\.xml$', re.I)
CACHE_SECONDS = 3600
MAX_CANDIDATES = 3
MIN_SHARED_TERMS = 2
STOPWORDS = {
    'about', 'after', 'against', 'also', 'article', 'been', 'claim', 'claiming', 'claims',
    'facebook', 'fact', 'from', 'have', 'made', 'make', 'news', 'post', 'posts', 'said',
    'says', 'that', 'their', 'there', 'this', 'video', 'viral', 'were', 'what', 'when',
    'which', 'with', 'would', 'photo', 'check', 'checks',
}
_cache: Dict[str, Dict[str, object]] = {}


def _terms(text: str) -> set:
    return {word for word in re.findall(r"[^\W_]+", str(text or '').lower())
            if len(word) >= 4 and word not in STOPWORDS}


def _get(url: str) -> Optional[str]:
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"})
        response.raise_for_status()
        return response.text
    except Exception as error:  # pragma: no cover - network failure must never break a check
        event('factcheck.index_unavailable', url=url, error=type(error).__name__)
        return None


def recent_article_urls(sitemap_url: str, pages: int = RECENT_SITEMAP_PAGES) -> List[str]:
    """Article URLs from the newest pages of a publisher's sitemap, cached in process."""
    cached = _cache.get(sitemap_url)
    if cached and time.time() - float(cached['fetched']) < CACHE_SECONDS:
        return list(cached['urls'])
    if requests is None:
        return []
    index = _get(sitemap_url)
    if not index:
        return []
    locations = [url for url in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", index) if url.endswith('.xml')]
    # Article pages only: a sitemap index also lists tag, category and author pages.
    sitemaps = [url for url in locations if ARTICLE_SITEMAP.search(url)] or locations or [sitemap_url]
    urls: List[str] = []
    for sitemap in sitemaps[-pages:]:
        page = index if sitemap == sitemap_url else _get(sitemap)
        if not page:
            continue
        urls.extend(url for url in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", page)
                    if not url.endswith('.xml'))
    _cache[sitemap_url] = {'fetched': time.time(), 'urls': urls}
    event('factcheck.index_loaded', sitemap=sitemap_url, urls=len(urls))
    return urls


def _title_from_url(url: str) -> str:
    slug = urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1]
    return ' '.join(word.capitalize() for word in slug.replace('-', ' ').split())


def matching_articles(claim: str, source: Dict[str, object], limit: int = MAX_CANDIDATES) -> List[Dict[str, object]]:
    """Recent articles of this source whose address shares the claim's distinctive words."""
    wanted = _terms(claim)
    if not wanted or not source.get('sitemap'):
        return []
    scored = []
    for url in recent_article_urls(str(source['sitemap'])):
        url = clean_article_url(url)
        if not url or article_url_rejection(url, source['name']):
            continue
        shared = wanted & _terms(urlsplit(url).path)
        if len(shared) >= MIN_SHARED_TERMS:
            scored.append((len(shared), url, sorted(shared)))
    scored.sort(key=lambda item: -item[0])
    return [{'source': source['name'], 'title': _title_from_url(url), 'url': url,
             'description': '', 'extra_snippets': [], 'matched_terms': shared}
            for _, url, shared in scored[:limit]]


@traced('retrieval.fact_check_index', dependency=False)
def fact_check_candidates(claim: str, limit: int = MAX_CANDIDATES) -> List[Dict[str, object]]:
    """Fact-check articles matching this claim, from the fact-checkers' own sitemaps."""
    candidates: List[Dict[str, object]] = []
    for source in get_fact_check_sources():
        candidates.extend(matching_articles(claim, source, limit))
    if candidates:
        event('factcheck.index_candidates',
              candidates=[{'url': c['url'], 'matched_terms': c['matched_terms']} for c in candidates])
    return candidates
