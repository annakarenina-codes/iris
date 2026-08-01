"""Local keyword-overlap fallback for low-confidence verdicts."""

from __future__ import annotations

import re
from typing import Dict, List


STOP_WORDS = {
    "about",
    "after",
    "also",
    "and",
    "ang",
    "are",
    "for",
    "from",
    "has",
    "have",
    "into",
    "ng",
    "the",
    "this",
    "that",
    "was",
    "were",
    "with",
}


def _tokens(text: str) -> List[str]:
    raw_tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [
        token
        for token in raw_tokens
        if token not in STOP_WORDS and len(token) >= 3
    ]


def _article_text(article: Dict[str, object]) -> str:
    return " ".join([
        str(article.get("title") or ""),
        str(article.get("description") or ""),
        str(article.get("text") or ""),
    ])


def keyword_overlap_verdict(claim: str, articles: List[Dict[str, object]]) -> Dict[str, object]:
    """Scores claim/evidence overlap without calling any external AI API."""
    claim_tokens = set(_tokens(claim))
    extracted_articles = [
        article
        for article in articles
        if article.get("status") == "extracted" and article.get("text")
    ]

    if not claim_tokens or not extracted_articles:
        return {
            "verdict": "Not Found",
            "reason": "No readable evidence was available for local keyword fallback.",
            "keyword_overlap": 0.0,
            "matched_keywords": [],
            "fallback_method": "keyword_overlap",
        }

    best_article = None
    best_matches = set()

    for article in extracted_articles:
        evidence_tokens = set(_tokens(_article_text(article)))
        matches = claim_tokens.intersection(evidence_tokens)

        if len(matches) > len(best_matches):
            best_article = article
            best_matches = matches

    overlap = round(len(best_matches) / len(claim_tokens), 4)
    verdict = "Partially Verified" if overlap >= 0.45 else "Not Found"

    if verdict == "Partially Verified":
        reason = (
            "OpenAI fallback was unavailable, but local keyword overlap found "
            f"{round(overlap * 100, 1)}% claim/evidence term overlap."
        )
    else:
        reason = (
            "OpenAI fallback was unavailable, and local keyword overlap did not "
            "find enough evidence support."
        )

    return {
        "verdict": verdict,
        "reason": reason,
        "keyword_overlap": overlap,
        "matched_keywords": sorted(best_matches),
        "fallback_method": "keyword_overlap",
        "primary_keyword_source": {
            "source": best_article.get("source"),
            "title": best_article.get("title"),
            "url": best_article.get("url"),
        } if best_article else None,
    }
