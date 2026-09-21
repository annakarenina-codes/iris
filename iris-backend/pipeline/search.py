"""
Brave Search integration for IRIS.

This module searches the fact-checking sources first (VERA Files, Rappler), then
the approved Philippine news sources. It can also run a backup search using the
original Tagalog/Taglish text when the translated English query returns too few
results.

Publishers that block automated downloads are read through the article passages
Brave returns for each result ("search excerpts") instead of downloading pages.
"""

from __future__ import annotations

from iris_trace.core import traced, submit_context

from collections import deque
from concurrent.futures import ThreadPoolExecutor
import html
import os
import re
import threading
import time
from typing import Dict, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover - depends on local environment setup
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment setup
    def load_dotenv():
        return False

from pipeline.article_extractor import extract_article_text
from pipeline.fact_check_index import fact_check_candidates
from pipeline.publisher_api import article_from_api
from pipeline.sources import get_all_sources, uses_search_excerpts
from pipeline.evidence_urls import article_url_rejection, clean_article_url


load_dotenv()


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Reads a positive integer environment setting with a safe default."""
    try:
        value = int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default

    return max(minimum, value)


def _worker_count(configured_workers: int, item_count: int) -> int:
    """Caps worker count to available work while keeping at least one worker."""
    return min(max(1, configured_workers), max(1, item_count))


BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
REQUEST_TIMEOUT_SECONDS = 10
RESULTS_PER_SOURCE = 5
MIN_RESULTS_BEFORE_BACKUP = 2
MAX_ARTICLES_PER_SOURCE = 3
# Sitemap matches take at most two of a fact-checker's slots, leaving room for search hits.
MAX_INDEX_ARTICLES = 2
RECENCY_WINDOW = "pm"  # Brave freshness: past month. Ranks recent coverage; never evidence.
SEARCH_RATE_LIMIT_RETRY_SECONDS = 1.5
MIN_EXCERPT_WORDS = 8
# Eleven sources, so one pass is one wave of requests rather than eight and then three.
MAX_SEARCH_WORKERS = _env_int("IRIS_SEARCH_WORKERS", 11)
MAX_ARTICLE_EXTRACTION_WORKERS = _env_int("IRIS_ARTICLE_WORKERS", 8)
# The Brave plan answers 50 requests a second. Passes and claims now search at the same time,
# so every request in the process takes its turn here and the sum stays under the plan's limit.
BRAVE_REQUESTS_PER_SECOND = _env_int("IRIS_BRAVE_REQUESTS_PER_SECOND", 40)


class _RequestPace:
    """At most `per_second` requests start in any one-second window, across every thread."""

    def __init__(self, per_second: int):
        self.per_second = per_second
        self._started: deque = deque()
        self._lock = threading.Lock()

    def wait_turn(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._started and now - self._started[0] >= 1.0:
                    self._started.popleft()
                if len(self._started) < self.per_second:
                    self._started.append(now)
                    return
                delay = 1.0 - (now - self._started[0])
            time.sleep(max(delay, 0.01))


_BRAVE_PACE = _RequestPace(BRAVE_REQUESTS_PER_SECOND)


def _get_api_key() -> Optional[str]:
    """Supports either .env variable name, so setup is more forgiving."""
    return os.getenv("BRAVE_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY")


# Brave refuses a query of more than 400 characters or 50 words, its site filter included, with
# HTTP 422. Attributed claims are searched with their whole sentence, and one keeping a Filipino
# quotation can run past that: in saved case A08 two claims of 599 and 520 characters failed on
# every source, and the check reported that the sources could not be reached.
MAX_QUERY_CHARACTERS = 400
MAX_QUERY_WORDS = 50


def _build_domain_query(query: str, site_query: str) -> str:
    """
    Combines the claim with a site: filter for Brave Search, within Brave's query limits.

    Straight double quotes are removed: Brave reads them as "this exact phrase", so a quotation
    typed with them was searched word for word, and a report that worded or transcribed it a
    little differently could not be found. In saved case A02 the five quotation claims got 2, 1,
    0, 0 and 1 results that way. Curly quotes were never read as phrases, so a post's typography
    decided how it was searched. A query too long for Brave keeps its opening words, which name
    the speaker and the subject.
    """
    site = str(site_query or "").strip()
    room = MAX_QUERY_CHARACTERS - (len(site) + 1 if site else 0)
    kept: List[str] = []
    for word in str(query or "").replace('"', " ").split()[:MAX_QUERY_WORDS - len(site.split())]:
        if len(" ".join([*kept, word])) > room:
            break
        kept.append(word)
    return " ".join([*kept, site]).strip()


@traced('retrieval.source_search', dependency=True)
def brave_search(
    query: str,
    source: Dict[str, object],
    count: int = RESULTS_PER_SOURCE,
    freshness: Optional[str] = None,
) -> Dict[str, object]:
    """
    Searches one source domain using Brave Search.

    freshness optionally restricts results to recent pages (for example "pm").
    Returns a consistent dictionary whether the request succeeds or fails.
    """
    api_key = _get_api_key()
    if requests is None:
        return {
            "source": source["name"],
            "query": query,
            "status": "missing_dependency",
            "error": "The requests package is not installed.",
            "results": [],
        }

    if not api_key:
        return {
            "source": source["name"],
            "query": query,
            "status": "missing_api_key",
            "error": "Missing BRAVE_API_KEY or BRAVE_SEARCH_API_KEY in .env.",
            "results": [],
        }

    domain_query = _build_domain_query(query, source["site_query"])
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": domain_query,
        "count": count,
        "country": "PH",
        "search_lang": "en",
        "safesearch": "moderate",
        "extra_snippets": "true",
    }
    if freshness:
        params["freshness"] = freshness

    try:
        _BRAVE_PACE.wait_turn()
        response = requests.get(
            BRAVE_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if getattr(response, "status_code", None) == 429:
            time.sleep(SEARCH_RATE_LIMIT_RETRY_SECONDS)
            _BRAVE_PACE.wait_turn()
            response = requests.get(
                BRAVE_SEARCH_URL,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as error:
        return {
            "source": source["name"],
            "query": domain_query,
            "status": "error",
            "error": f"Search request failed: {error}",
            "results": [],
        }
    except ValueError as error:
        return {
            "source": source["name"],
            "query": domain_query,
            "status": "error",
            "error": f"Search response was not valid JSON: {error}",
            "results": [],
        }

    web_results = payload.get("web", {}).get("results", [])
    results = []
    rejected_results = []

    for item in web_results:
        url = clean_article_url(item.get("url"))
        if not url:
            continue
        rejection = article_url_rejection(url, source['name'])
        if rejection:
            rejected_results.append({'url': url, 'reason': rejection})
            continue

        results.append({
            "source": source["name"],
            "title": item.get("title"),
            "url": url,
            "description": item.get("description"),
            "extra_snippets": [
                snippet for snippet in (item.get("extra_snippets") or [])
                if isinstance(snippet, str)
            ],
        })

    return {
        "source": source["name"],
        "query": domain_query,
        "status": "ok",
        "error": None,
        "results": results,
        "rejected_results": rejected_results,
    }


def _search_error_report(query: str, source: Dict[str, object], error: Exception) -> Dict[str, object]:
    source_name = source.get("name", "Unknown source")
    site_query = source.get("site_query", "")

    return {
        "source": source_name,
        "query": _build_domain_query(query, str(site_query)),
        "status": "error",
        "error": f"Search request failed unexpectedly: {error}",
        "results": [],
    }


def _safe_brave_search(query: str, source: Dict[str, object], freshness: Optional[str] = None) -> Dict[str, object]:
    try:
        if freshness:
            return brave_search(query, source, freshness=freshness)
        return brave_search(query, source)
    except Exception as error:  # pragma: no cover - defensive safety net
        return _search_error_report(query, source, error)


def search_sources(query: str, freshness: Optional[str] = None, search_pass: str = "primary") -> Dict[str, object]:
    """Searches the fact-checking sources first, then the approved news sources."""
    sources = get_all_sources()
    all_results = []

    with ThreadPoolExecutor(
        max_workers=_worker_count(MAX_SEARCH_WORKERS, len(sources))
    ) as executor:
        futures = [
            submit_context(executor, _safe_brave_search, query, source, freshness)
            for source in sources
        ]
        source_reports = [future.result() for future in futures]

    for report in source_reports:
        for rank, result in enumerate(report["results"]):
            all_results.append({**result, "search_pass": search_pass, "pass_rank": rank})

    return {
        "query": query,
        "search_pass": search_pass,
        "freshness": freshness,
        "total_results": len(all_results),
        "results": all_results,
        "source_reports": source_reports,
    }


def _interleave_pass_results(searches: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """
    Orders results so every search pass contributes its best hits per source.

    Results are grouped by source later, so ordering by (rank within source,
    pass order) lets each pass's top result be read before any pass's second.
    """
    ordered = []
    for pass_index, search in enumerate(searches):
        for result in search["results"]:
            ordered.append((result.get("pass_rank", 0), pass_index, result))
    ordered.sort(key=lambda item: (item[0], item[1]))

    combined, seen_urls = [], set()
    for _, _, result in ordered:
        if result["url"] not in seen_urls:
            seen_urls.add(result["url"])
            combined.append(result)
    return combined


@traced('retrieval.queries', dependency=False)
def fact_check_search(claim_text: str) -> Dict[str, object]:
    """A pass over the fact-checkers' own sitemaps, for articles web search does not return."""
    results = [{**result, 'search_pass': 'fact_check_index', 'pass_rank': rank}
               for rank, result in enumerate(fact_check_candidates(claim_text, MAX_INDEX_ARTICLES))]
    return {'query': claim_text, 'search_pass': 'fact_check_index', 'freshness': None,
            'total_results': len(results), 'results': results, 'source_reports': []}


def search_with_backup(
    primary_query: str,
    backup_query: Optional[str] = None,
    original_language_query: Optional[str] = None,
    recency: bool = True,
    fact_check_text: Optional[str] = None,
    translated_query: Optional[str] = None,
) -> Dict[str, object]:
    """
    Runs every search pass for one claim and merges their results.

    0. fact_check_index: fact-checks found in a fact-checker's own sitemap, first so a
       targeted match is always read.
    1. primary: the claim's own query.
    2. recent: the same query restricted to recent pages, so current coverage
       is not pushed out by older articles on the same subject.
    3. original_language: the post's own Filipino/Taglish sentence, when given.
    4. translated: an English rendering of a quotation the claim keeps in its own language.
    5. backup: the older fallback, only when too few results were found.

    The passes are independent, so they run at the same time: one after another they cost a
    claim about eight seconds of waiting on Brave (saved case B10). Results are still merged in
    pass order, so what is read does not depend on which request answered first.
    """
    passes = [(primary_query, None, "primary")]
    if recency:
        passes.append((primary_query, RECENCY_WINDOW, "recent"))

    used_queries = {primary_query.strip().casefold()}
    original_language_query = (original_language_query or "").strip()
    translated_query = (translated_query or "").strip()
    for name, query in (("original_language", original_language_query), ("translated", translated_query)):
        if query and query.casefold() not in used_queries:
            passes.append((query, None, name))
            used_queries.add(query.casefold())

    with ThreadPoolExecutor(max_workers=len(passes) + 1, thread_name_prefix="iris-pass") as executor:
        pass_futures = [submit_context(executor, search_sources, query, freshness, name)
                        for query, freshness, name in passes]
        index_future = submit_context(executor, fact_check_search, fact_check_text or primary_query)
        searches = [future.result() for future in pass_futures]
        fact_checks = index_future.result()

    # The index lookup exists because web search misses these articles, so its candidate must
    # not be pushed out of the fact-checker's three article slots by ordinary search hits: the
    # VERA Files fact-check that settles a claim was lost this way.
    if fact_checks['results']:
        searches.insert(0, fact_checks)

    combined_results = _interleave_pass_results(searches)
    should_backup = bool(
        backup_query
        and backup_query.strip()
        and backup_query.strip().casefold() not in used_queries
        and len(combined_results) < MIN_RESULTS_BEFORE_BACKUP
    )

    if should_backup:
        searches.append(search_sources(backup_query, search_pass="backup"))
        combined_results = _interleave_pass_results(searches)

    return {
        "primary_query": primary_query,
        "backup_query_used": should_backup,
        "original_language_query": original_language_query or None,
        "translated_query": translated_query or None,
        "search_passes": [search["search_pass"] for search in searches],
        "total_results": len(combined_results),
        "results": combined_results,
        "searches": searches,
    }


def _get_source_names(search_result: Dict[str, object]) -> List[str]:
    """Keeps source order from the approved source search reports."""
    source_names = []

    for search in search_result["searches"]:
        for report in search["source_reports"]:
            source_name = report["source"]
            if source_name not in source_names:
                source_names.append(source_name)

    return source_names


def _group_results_by_source(search_result: Dict[str, object]) -> Dict[str, List[Dict[str, object]]]:
    """Groups Brave result links under their source names."""
    grouped_results: Dict[str, List[Dict[str, object]]] = {
        source_name: [] for source_name in _get_source_names(search_result)
    }

    seen_urls = set()
    for result in search_result["results"]:
        url = result["url"]
        if url in seen_urls:
            continue

        seen_urls.add(url)
        grouped_results.setdefault(result["source"], []).append(result)

    return grouped_results


def _build_source_summary(search_result: Dict[str, object], articles: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Builds a per-source summary for Postman and the future UI."""
    grouped_results = _group_results_by_source(search_result)
    summary = []

    for source_name in _get_source_names(search_result):
        source_articles = [
            article for article in articles if article["source"] == source_name
        ]
        extracted_count = len([
            article for article in source_articles if article["status"] == "extracted"
        ])

        summary.append({
            "source": source_name,
            "results_found": len(grouped_results.get(source_name, [])),
            "articles_checked": len(source_articles),
            "articles_extracted": extracted_count,
        })

    return summary


def _article_url_key(article: Dict[str, object]) -> str:
    """Normalizes article URLs enough for evidence-pool deduping."""
    return str(article.get("url") or "").strip().rstrip("/").lower()


def _tag_articles(
    articles: List[Dict[str, object]],
    evidence_pool: str,
) -> List[Dict[str, object]]:
    tagged_articles = []
    for article in articles:
        tagged_article = dict(article)
        tagged_article.setdefault("evidence_pool", evidence_pool)
        tagged_articles.append(tagged_article)

    return tagged_articles


def _merge_articles(
    primary_articles: List[Dict[str, object]],
    supplemental_articles: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    merged_articles = []
    seen_urls = set()

    for article in [
        *_tag_articles(primary_articles, "claim_specific"),
        *_tag_articles(supplemental_articles, "event_context"),
    ]:
        url_key = _article_url_key(article)
        if url_key and url_key in seen_urls:
            continue

        if url_key:
            seen_urls.add(url_key)
        merged_articles.append(article)

    return merged_articles


def _merge_source_summary(
    primary_summary: List[Dict[str, object]],
    supplemental_summary: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    order = []
    by_source: Dict[str, Dict[str, object]] = {}

    for summary in [*primary_summary, *supplemental_summary]:
        source = str(summary.get("source") or "Unknown source")
        if source not in by_source:
            by_source[source] = {
                "source": source,
                "results_found": 0,
                "articles_checked": 0,
                "articles_extracted": 0,
            }
            order.append(source)

        by_source[source]["results_found"] += int(summary.get("results_found") or 0)
        by_source[source]["articles_checked"] += int(summary.get("articles_checked") or 0)
        by_source[source]["articles_extracted"] += int(summary.get("articles_extracted") or 0)

    return [by_source[source] for source in order]


@traced('retrieval.merge', dependency=False)
def merge_search_results(
    primary_result: Dict[str, object],
    supplemental_result: Optional[Dict[str, object]],
) -> Dict[str, object]:
    """
    Adds shared event-level evidence to a claim-specific search result.

    The claim-specific result stays first for ranking stability, while event
    articles are added as supplementary candidates and deduped by URL.
    """
    if not supplemental_result:
        return primary_result

    primary_articles = list(primary_result.get("articles") or [])
    supplemental_articles = list(supplemental_result.get("articles") or [])
    merged_articles = _merge_articles(primary_articles, supplemental_articles)
    extracted_articles = [
        article for article in merged_articles if article.get("status") == "extracted"
    ]

    primary_search = primary_result.get("search") or {}
    supplemental_search = supplemental_result.get("search") or {}

    return {
        "total_search_results": (
            int(primary_result.get("total_search_results") or 0)
            + int(supplemental_result.get("total_search_results") or 0)
        ),
        "searched_articles": len(merged_articles),
        "extracted_articles": len(extracted_articles),
        "articles": merged_articles,
        "source_summary": _merge_source_summary(
            list(primary_result.get("source_summary") or []),
            list(supplemental_result.get("source_summary") or []),
        ),
        "search": {
            "primary_query": primary_search.get("primary_query"),
            "backup_query_used": bool(primary_search.get("backup_query_used"))
            or bool(supplemental_search.get("backup_query_used")),
            "total_results": (
                int(primary_search.get("total_results") or primary_result.get("total_search_results") or 0)
                + int(supplemental_search.get("total_results") or supplemental_result.get("total_search_results") or 0)
            ),
            "results": [
                *(primary_search.get("results") or []),
                *(supplemental_search.get("results") or []),
            ],
            "searches": [
                *(primary_search.get("searches") or []),
                *(supplemental_search.get("searches") or []),
            ],
            "supplemental_event_query": supplemental_search.get("primary_query"),
        },
        "merged_evidence_pool": {
            "claim_specific_articles": len(primary_articles),
            "event_context_articles": len(supplemental_articles),
        },
    }


def _article_error_result(url: str, error: Exception) -> Dict[str, object]:
    return {
        "url": url,
        "status": "error",
        "error": f"Could not extract article unexpectedly: {error}",
        "title": None,
        "text": "",
        "word_count": 0,
    }


def _clean_excerpt(text: object) -> str:
    """Removes Brave's highlight markup and entities from one returned passage."""
    cleaned = html.unescape(re.sub(r"<[^>]+>", "", str(text or "")))
    return re.sub(r"\s+", " ", cleaned).strip()


def _excerpt_passages(result: Dict[str, object]) -> List[str]:
    """Returns the distinct article passages Brave supplied for one result."""
    passages: List[str] = []
    for candidate in [result.get("description"), *(result.get("extra_snippets") or [])]:
        passage = _clean_excerpt(candidate)
        if not passage:
            continue
        key = passage.casefold()
        if any(key in existing.casefold() for existing in passages):
            continue
        passages = [existing for existing in passages if existing.casefold() not in key]
        passages.append(passage)
    return passages


@traced('retrieval.search_excerpt', dependency=False)
def build_excerpt_article(result: Dict[str, object], reason: str) -> Dict[str, object]:
    """
    Builds an evidence record from the search API's article passages.

    The passages are the publisher's own text as returned by the search API.
    They are shorter than the full article, so the record is labeled
    search_excerpt and never presented as a full-text read.
    """
    url = result["url"]
    rejection = article_url_rejection(url, result.get("source"))
    passages = _excerpt_passages(result)
    text = "\n".join(passages)
    words = len(text.split())
    usable = not rejection and words >= MIN_EXCERPT_WORDS

    return {
        "source": result.get("source"),
        "title": _clean_excerpt(result.get("title")) or url,
        "url": url,
        "description": _clean_excerpt(result.get("description")),
        "status": "extracted" if usable else "skipped",
        "word_count": words if usable else 0,
        "error": None if usable else (rejection or "Search excerpt is empty or too short."),
        "extraction_method": "search_excerpt",
        "extraction_quality": "excerpt",
        "evidence_type": "search_excerpt",
        "excerpt_reason": reason,
        "text": text if usable else "",
    }


def _build_article_from_result(result: Dict[str, object]) -> Dict[str, object]:
    url = result["url"]

    if uses_search_excerpts(result.get("source")):
        return build_excerpt_article(result, "publisher_blocks_automated_download")

    try:
        # A publisher that offers an article API is read there first: VERA Files serves its
        # pages behind a challenge, and the API is the channel it offers to programs.
        extraction = article_from_api(url, result.get("source")) or extract_article_text(url)
    except Exception as error:  # pragma: no cover - defensive safety net
        extraction = _article_error_result(url, error)

    if extraction.get("status") == "error" and _excerpt_passages(result):
        fallback = build_excerpt_article(result, "download_failed")
        if fallback["status"] == "extracted":
            fallback["download_error"] = extraction.get("error")
            return fallback

    return {
        "source": result.get("source"),
        "title": extraction.get("title") or result.get("title"),
        "url": extraction.get("url") or url,
        # Carried from the publisher's own section labels; a URL alone cannot show it.
        "sections": extraction.get("sections") or [],
        "is_opinion": bool(extraction.get("is_opinion")),
        "description": extraction.get("description") or result.get("description"),
        "status": extraction.get("status"),
        "word_count": extraction.get("word_count", 0),
        "error": extraction.get("error"),
        "extraction_method": extraction.get("extraction_method"),
        "extraction_quality": extraction.get("extraction_quality"),
        "evidence_type": "full_text",
        "text": extraction.get("text", ""),
    }


def _article_targets_by_source_order(
    search_result: Dict[str, object],
    max_articles_per_source: int,
) -> List[Dict[str, object]]:
    grouped_results = _group_results_by_source(search_result)
    article_targets: List[Dict[str, object]] = []

    for source_name in _get_source_names(search_result):
        source_results = grouped_results.get(source_name, [])
        article_targets.extend(source_results[:max_articles_per_source])

    return article_targets


def _extract_articles_parallel(article_targets: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if not article_targets:
        return []

    with ThreadPoolExecutor(
        max_workers=_worker_count(MAX_ARTICLE_EXTRACTION_WORKERS, len(article_targets))
    ) as executor:
        futures = [
            submit_context(executor, _build_article_from_result, result)
            for result in article_targets
        ]
        return [future.result() for future in futures]


@traced('retrieval.pool', dependency=False)
def search_and_extract(
    primary_query: str,
    backup_query: Optional[str] = None,
    max_articles_per_source: int = MAX_ARTICLES_PER_SOURCE,
    original_language_query: Optional[str] = None,
    fact_check_text: Optional[str] = None,
    translated_query: Optional[str] = None,
) -> Dict[str, object]:
    """
    Searches approved sources and extracts readable article text from each source.

    This keeps the evidence pool balanced. The fact-checking sources are still
    first, but the extractor also checks article links from every news source.
    """
    search_result = search_with_backup(
        primary_query,
        backup_query,
        original_language_query=original_language_query,
        fact_check_text=fact_check_text,
        translated_query=translated_query,
    )
    article_targets = _article_targets_by_source_order(
        search_result,
        max_articles_per_source,
    )
    articles = _extract_articles_parallel(article_targets)

    extracted_articles = [article for article in articles if article["status"] == "extracted"]

    return {
        "total_search_results": search_result["total_results"],
        "searched_articles": len(articles),
        "extracted_articles": len(extracted_articles),
        "articles": articles,
        "source_summary": _build_source_summary(search_result, articles),
        "search": search_result,
    }
