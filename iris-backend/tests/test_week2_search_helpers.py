"""
Simple Week 2 helper checks.

Run from the iris-backend folder:
    python tests/test_week2_search_helpers.py

These checks do not call Brave Search, so they are safe to run without using API
credits.
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

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
    assert len(news_sources) == 6
    assert len(all_sources) == 7
    assert all_sources[0]["name"] == "VERA Files"

    query = _build_domain_query("sample claim", "site:verafiles.org")
    assert query == "sample claim site:verafiles.org"

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

    print("All Week 2 helper checks passed.")
    print("Approved sources checked: 7 total, VERA Files first.")
    print("No Brave API credits were used by this test.")


if __name__ == "__main__":
    run_checks()
