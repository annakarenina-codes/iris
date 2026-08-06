"""
Brave Search integration for IRIS.

This module searches VERA Files first, then the six approved Philippine news
sources. It can also run a backup search using the original Tagalog/Taglish
text when the translated English query returns too few results.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
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
from pipeline.sources import get_all_sources


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
RESULTS_PER_SOURCE = 3
MIN_RESULTS_BEFORE_BACKUP = 2
MAX_ARTICLES_PER_SOURCE = 2
MAX_SEARCH_WORKERS = _env_int("IRIS_SEARCH_WORKERS", 7)
MAX_ARTICLE_EXTRACTION_WORKERS = _env_int("IRIS_ARTICLE_WORKERS", 8)


def _get_api_key() -> Optional[str]:
    """Supports either .env variable name, so setup is more forgiving."""
    return os.getenv("BRAVE_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY")


def _build_domain_query(query: str, site_query: str) -> str:
    """Combines the claim with a site: filter for Brave Search."""
    return f"{query} {site_query}".strip()


def brave_search(query: str, source: Dict[str, object], count: int = RESULTS_PER_SOURCE) -> Dict[str, object]:
    """
    Searches one source domain using Brave Search.

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
    }

    try:
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

    for item in web_results:
        url = item.get("url")
        if not url:
            continue

        results.append({
            "source": source["name"],
            "title": item.get("title"),
            "url": url,
            "description": item.get("description"),
        })

    return {
        "source": source["name"],
        "query": domain_query,
        "status": "ok",
        "error": None,
        "results": results,
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


def _safe_brave_search(query: str, source: Dict[str, object]) -> Dict[str, object]:
    try:
        return brave_search(query, source)
    except Exception as error:  # pragma: no cover - defensive safety net
        return _search_error_report(query, source, error)


def search_sources(query: str) -> Dict[str, object]:
    """Searches VERA Files first, then the six approved Philippine sources."""
    sources = get_all_sources()
    all_results = []

    with ThreadPoolExecutor(
        max_workers=_worker_count(MAX_SEARCH_WORKERS, len(sources))
    ) as executor:
        futures = [
            executor.submit(_safe_brave_search, query, source)
            for source in sources
        ]
        source_reports = [future.result() for future in futures]

    for report in source_reports:
        all_results.extend(report["results"])

    return {
        "query": query,
        "total_results": len(all_results),
        "results": all_results,
        "source_reports": source_reports,
    }


def search_with_backup(primary_query: str, backup_query: Optional[str] = None) -> Dict[str, object]:
    """
    Runs the translated English search first.

    If fewer than two results are found and a different original Tagalog/Taglish
    query is available, it runs one backup search.
    """
    primary = search_sources(primary_query)
    searches = [primary]
    combined_results = list(primary["results"])

    should_backup = (
        backup_query
        and backup_query.strip()
        and backup_query.strip().lower() != primary_query.strip().lower()
        and primary["total_results"] < MIN_RESULTS_BEFORE_BACKUP
    )

    if should_backup:
        backup = search_sources(backup_query)
        searches.append(backup)

        seen_urls = {result["url"] for result in combined_results}
        for result in backup["results"]:
            if result["url"] not in seen_urls:
                combined_results.append(result)
                seen_urls.add(result["url"])

    return {
        "primary_query": primary_query,
        "backup_query_used": should_backup,
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


def _article_error_result(url: str, error: Exception) -> Dict[str, object]:
    return {
        "url": url,
        "status": "error",
        "error": f"Could not extract article unexpectedly: {error}",
        "title": None,
        "text": "",
        "word_count": 0,
    }


def _build_article_from_result(result: Dict[str, object]) -> Dict[str, object]:
    url = result["url"]

    try:
        extraction = extract_article_text(url)
    except Exception as error:  # pragma: no cover - defensive safety net
        extraction = _article_error_result(url, error)

    return {
        "source": result.get("source"),
        "title": extraction.get("title") or result.get("title"),
        "url": url,
        "description": result.get("description"),
        "status": extraction.get("status"),
        "word_count": extraction.get("word_count", 0),
        "error": extraction.get("error"),
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
            executor.submit(_build_article_from_result, result)
            for result in article_targets
        ]
        return [future.result() for future in futures]


def search_and_extract(
    primary_query: str,
    backup_query: Optional[str] = None,
    max_articles_per_source: int = MAX_ARTICLES_PER_SOURCE
) -> Dict[str, object]:
    """
    Searches approved sources and extracts readable article text from each source.

    This keeps the evidence pool balanced. VERA Files is still first, but the
    extractor also checks article links from the six approved news sources.
    """
    search_result = search_with_backup(primary_query, backup_query)
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
