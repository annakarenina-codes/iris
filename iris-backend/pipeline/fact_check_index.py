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
import threading
import time
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Dict, List, Optional
from urllib.parse import urlsplit

try:
    import requests
except ImportError:  # pragma: no cover - depends on local environment setup
    requests = None

from pipeline.evidence_urls import article_url_rejection, clean_article_url
from pipeline.sources import get_fact_check_sources

# A sitemap is read in the background, so it may take as long as the publisher needs: the newest
# VERA Files page was 627 KB and took 23 seconds on 22 September, past the old ten-second limit.
REQUEST_TIMEOUT_SECONDS = 30
RECENT_SITEMAP_PAGES = 2          # newest pages only: recent fact-checks, not the whole archive
ARTICLE_SITEMAP = re.compile(r'/(?:post|article|news)-sitemap\d*\.xml$', re.I)
CACHE_SECONDS = 3600
# An index missing a page that failed is used as it is, and read again in the background after
# ten minutes rather than kept for an hour.
PARTIAL_CACHE_SECONDS = 600
# How long a claim waits for an index that has never been read. Every later claim is answered
# from memory at once, and a stale index is refreshed behind it rather than in front of it.
LOOKUP_WAIT_SECONDS = 6
MAX_CANDIDATES = 3
MIN_SHARED_TERMS = 2
STOPWORDS = {
    'about', 'after', 'against', 'also', 'article', 'been', 'claim', 'claiming', 'claims',
    'facebook', 'fact', 'from', 'have', 'made', 'make', 'news', 'post', 'posts', 'said',
    'says', 'that', 'their', 'there', 'this', 'video', 'viral', 'were', 'what', 'when',
    'which', 'with', 'would', 'photo', 'check', 'checks',
}
_cache: Dict[str, Dict[str, object]] = {}
_loading: Dict[str, Future] = {}
_loading_guard = threading.Lock()


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


def _load(sitemap_url: str, pages: int) -> List[str]:
    """Reads the sitemap index and its newest article pages, and keeps what was read."""
    index = _get(sitemap_url)
    if not index:
        return []
    locations = [url for url in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", index) if url.endswith('.xml')]
    # Article pages only: a sitemap index also lists tag, category and author pages.
    sitemaps = [url for url in locations if ARTICLE_SITEMAP.search(url)] or locations or [sitemap_url]
    wanted = sitemaps[-pages:]
    with ThreadPoolExecutor(max_workers=max(1, len(wanted))) as executor:
        read = list(executor.map(lambda sitemap: index if sitemap == sitemap_url else _get(sitemap), wanted))
    urls: List[str] = []
    for page in read:
        if page:
            urls.extend(url for url in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", page)
                        if not url.endswith('.xml'))
    complete = all(read)
    _cache[sitemap_url] = {'fetched': time.time(), 'urls': urls,
                           'lifetime': CACHE_SECONDS if complete else PARTIAL_CACHE_SECONDS}
    event('factcheck.index_loaded', sitemap=sitemap_url, urls=len(urls), complete=complete)
    return urls


def _start_load(sitemap_url: str, pages: int) -> Future:
    """One background read per sitemap at a time; claims arriving together share it."""
    with _loading_guard:
        future = _loading.get(sitemap_url)
        if future is not None and not future.done():
            return future
        future = Future()
        _loading[sitemap_url] = future

    def read():
        try:
            future.set_result(_load(sitemap_url, pages))
        except Exception as error:  # pragma: no cover - a failed read leaves the old index in place
            future.set_result([])
            event('factcheck.index_unavailable', url=sitemap_url, error=type(error).__name__)

    # A daemon thread: a publisher taking half a minute must not keep the process from exiting.
    threading.Thread(target=read, name='iris-sitemap', daemon=True).start()
    return future


def recent_article_urls(sitemap_url: str, pages: int = RECENT_SITEMAP_PAGES,
                        wait: float = LOOKUP_WAIT_SECONDS) -> List[str]:
    """
    Article URLs from the newest pages of a publisher's sitemap.

    The lookup ran inside every claim's search, and the search waited for it: on 22 September a
    slow VERA Files page held each claim for 20 seconds after the web search had finished. An
    index already in memory is now answered at once, and one that is stale or incomplete is read
    again in the background. Only a first read is waited for, and never for long.
    """
    cached = _cache.get(sitemap_url)
    fresh = cached and time.time() - float(cached['fetched']) < float(cached.get('lifetime', CACHE_SECONDS))
    if fresh:
        return list(cached['urls'])
    if requests is None:
        return list(cached['urls']) if cached else []
    future = _start_load(sitemap_url, pages)
    if cached:
        return list(cached['urls'])
    try:
        return list(future.result(timeout=wait))
    except FutureTimeout:
        event('factcheck.index_pending', sitemap=sitemap_url, waited_seconds=wait)
        return []


def _title_from_url(url: str) -> str:
    slug = urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1]
    return ' '.join(word.capitalize() for word in slug.replace('-', ' ').split())


def matching_articles(claim: str, source: Dict[str, object], limit: int = MAX_CANDIDATES) -> List[Dict[str, object]]:
    """Recent articles of this source whose address shares the claim's distinctive words."""
    wanted = _terms(claim)
    if not wanted or not source.get('sitemap'):
        return []
    urls = [clean_article_url(url) for url in recent_article_urls(str(source['sitemap']))]
    urls = [url for url in urls if url and not article_url_rejection(url, source['name'])]
    # A name the archive mentions once identifies an article; "marcos" or "president" does not.
    # Counting matches alone let a general Marcos story outrank the fact-check naming the person.
    appearances = Counter(term for url in urls for term in _terms(urlsplit(url).path))
    scored = []
    for url in urls:
        shared = wanted & _terms(urlsplit(url).path)
        if len(shared) >= MIN_SHARED_TERMS:
            weight = sum(1 / appearances[term] for term in shared)
            scored.append((weight, url, sorted(shared)))
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
