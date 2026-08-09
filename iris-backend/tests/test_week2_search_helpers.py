"""
Simple Week 2 helper checks.

Run from the iris-backend folder:
    python tests/test_week2_search_helpers.py

These checks do not call Brave Search, so they are safe to run without using API
credits.
"""

from pathlib import Path
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pipeline.search as search_module
import pipeline.article_extractor as article_module
from pipeline.sources import get_all_sources, get_news_sources, get_vera_source
from pipeline.search import (
    _build_domain_query,
    _build_source_summary,
    _group_results_by_source,
)


def run_checks() -> None:
    vera = get_vera_source()
    news_sources = get_news_sources()
    all_sources = get_all_sources()

    assert vera["name"] == "VERA Files"
    assert vera["priority"] is True
    assert len(news_sources) == 7
    assert len(all_sources) == 8
    assert all_sources[0]["name"] == "VERA Files"
    assert news_sources[0]["name"] == "ABS-CBN News"
    assert news_sources[0]["site_query"] == "site:abs-cbn.com/news"

    query = _build_domain_query("sample claim", "site:verafiles.org")
    assert query == "sample claim site:verafiles.org"
    assert article_module.normalize_article_url(
        "https://www.abs-cbn.com/news/nation/2026/8/5/padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501."
    ) == (
        "https://www.abs-cbn.com/news/nation/2026/8/5/"
        "padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501"
    )
    if article_module.BeautifulSoup is not None:
        original_article_requests = article_module.requests
        requested = {}

        class FakeResponse:
            text = """
                <html>
                    <head>
                        <title>Fallback title</title>
                        <meta property="og:title" content="Padilla tests auditor on knowledge of terrorism, security threats">
                        <meta name="description" content="Senator Robinhood Padilla asked former state auditor Roderick Wamil about BARMM and terrorism threats.">
                    </head>
                    <body><main><p>Short article.</p></main></body>
                </html>
            """

            def raise_for_status(self):
                return None

        class FakeRequests:
            RequestException = Exception

            @staticmethod
            def get(url, headers=None, timeout=None):
                requested["url"] = url
                return FakeResponse()

        try:
            article_module.requests = FakeRequests
            article = article_module.extract_article_text(
                "https://www.abs-cbn.com/news/nation/2026/8/5/"
                "padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501."
            )
        finally:
            article_module.requests = original_article_requests

        assert requested["url"].endswith("security-threats-1501")
        assert article["status"] == "extracted"
        assert article["extraction_method"] == "metadata"
        assert "Padilla tests auditor" in article["text"]

    fake_search_result = {
        "results": [
            {"source": "VERA Files", "title": "A", "url": "https://verafiles.org/a"},
            {"source": "GMA News", "title": "B", "url": "https://gmanetwork.com/news/b"},
            {"source": "VERA Files", "title": "C", "url": "https://verafiles.org/c"},
        ],
        "searches": [
            {
                "source_reports": [
                    {"source": "VERA Files"},
                    {"source": "GMA News"},
                ]
            }
        ],
    }
    grouped = _group_results_by_source(fake_search_result)
    assert len(grouped["VERA Files"]) == 2
    assert len(grouped["GMA News"]) == 1

    fake_articles = [
        {"source": "VERA Files", "status": "extracted"},
        {"source": "GMA News", "status": "skipped"},
    ]
    summary = _build_source_summary(fake_search_result, fake_articles)
    assert summary[0]["source"] == "VERA Files"
    assert summary[0]["results_found"] == 2
    assert summary[0]["articles_extracted"] == 1

    originals = {
        "get_all_sources": search_module.get_all_sources,
        "brave_search": search_module.brave_search,
        "search_with_backup": search_module.search_with_backup,
        "extract_article_text": search_module.extract_article_text,
    }

    try:
        fake_sources = [
            {"name": "VERA Files", "site_query": "site:verafiles.org"},
            {"name": "GMA News", "site_query": "site:gmanetwork.com/news"},
            {"name": "Philippine Star", "site_query": "site:philstar.com"},
        ]

        def fake_brave_search(query, source):
            if source["name"] == "VERA Files":
                time.sleep(0.03)
            return {
                "source": source["name"],
                "query": f"{query} {source['site_query']}",
                "status": "ok",
                "error": None,
                "results": [
                    {
                        "source": source["name"],
                        "title": f"{source['name']} result",
                        "url": f"https://example.com/{source['name'].lower().replace(' ', '-')}",
                        "description": "Fake result.",
                    }
                ],
            }

        search_module.get_all_sources = lambda: fake_sources
        search_module.brave_search = fake_brave_search
        parallel_search = search_module.search_sources("sample claim")

        assert [report["source"] for report in parallel_search["source_reports"]] == [
            "VERA Files",
            "GMA News",
            "Philippine Star",
        ]
        assert [result["source"] for result in parallel_search["results"]] == [
            "VERA Files",
            "GMA News",
            "Philippine Star",
        ]

        fake_parallel_search_result = {
            "primary_query": "sample claim",
            "backup_query_used": False,
            "total_results": 3,
            "results": [
                {
                    "source": "VERA Files",
                    "title": "VERA A",
                    "url": "https://verafiles.org/a",
                    "description": "A",
                },
                {
                    "source": "VERA Files",
                    "title": "VERA B",
                    "url": "https://verafiles.org/b",
                    "description": "B",
                },
                {
                    "source": "GMA News",
                    "title": "GMA A",
                    "url": "https://gmanetwork.com/news/a",
                    "description": "C",
                },
            ],
            "searches": [
                {
                    "source_reports": [
                        {"source": "VERA Files"},
                        {"source": "GMA News"},
                    ]
                }
            ],
        }

        def fake_extract_article_text(url):
            if url.endswith("/a"):
                time.sleep(0.03)
            return {
                "url": url,
                "status": "extracted",
                "error": None,
                "title": f"Extracted {url}",
                "text": "Readable article text " * 10,
                "word_count": 120,
            }

        search_module.search_with_backup = lambda primary_query, backup_query=None: fake_parallel_search_result
        search_module.extract_article_text = fake_extract_article_text

        parallel_extract = search_module.search_and_extract(
            "sample claim",
            max_articles_per_source=1,
        )

        assert parallel_extract["searched_articles"] == 2
        assert parallel_extract["extracted_articles"] == 2
        assert [article["url"] for article in parallel_extract["articles"]] == [
            "https://verafiles.org/a",
            "https://gmanetwork.com/news/a",
        ]
        assert parallel_extract["source_summary"][0]["source"] == "VERA Files"
        assert parallel_extract["source_summary"][0]["articles_checked"] == 1
    finally:
        search_module.get_all_sources = originals["get_all_sources"]
        search_module.brave_search = originals["brave_search"]
        search_module.search_with_backup = originals["search_with_backup"]
        search_module.extract_article_text = originals["extract_article_text"]

    print("All Week 2 helper checks passed.")
    print("Approved sources checked: 8 total, VERA Files first.")
    print("No Brave API credits were used by this test.")


if __name__ == "__main__":
    run_checks()
