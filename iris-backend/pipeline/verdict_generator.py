"""
Similarity-based verdict generation for IRIS.

Week 3 uses sentence-transformers to compare the user claim against extracted
article text. No OpenAI is used here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from sentence_transformers import SentenceTransformer, util


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VERIFIED_THRESHOLD = 0.85
PARTIAL_THRESHOLD = 0.50
VERA_PRIORITY_BONUS = 0.03
DEFAULT_MODEL_CACHE = Path(__file__).resolve().parents[1] / ".hf_cache"
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    """Loads the embedding model once, then reuses it for future requests."""
    global _model

    if _model is None:
        cache_folder = os.getenv("IRIS_MODEL_CACHE", str(DEFAULT_MODEL_CACHE))
        _model = SentenceTransformer(MODEL_NAME, cache_folder=cache_folder)

    return _model


def _round_score(score: float) -> float:
    """Keeps similarity scores readable in JSON responses."""
    return round(float(score), 4)


def _get_verdict_label(best_score: float) -> str:
    """Maps similarity score to the thesis verdict labels."""
    if best_score >= VERIFIED_THRESHOLD:
        return "Verified"

    if best_score >= PARTIAL_THRESHOLD:
        return "Partially Verified"

    return "Not Found"


def _get_reason(verdict: str, best_score: float) -> str:
    """Creates a short user-facing explanation for the verdict."""
    score_percent = round(best_score * 100, 1)

    if verdict == "Verified":
        return (
            f"The claim strongly matches retrieved article evidence "
            f"with a top similarity score of {score_percent}%."
        )

    if verdict == "Partially Verified":
        return (
            f"The claim has related article evidence, but the top similarity "
            f"score is only {score_percent}%, so it is not fully verified yet."
        )

    return (
        "IRIS searched the approved sources, but no extracted article reached "
        "the minimum similarity threshold for support."
    )


def _score_article(claim_embedding, article: Dict[str, object]) -> Dict[str, object]:
    """Scores one extracted article against the claim."""
    article_text = article.get("text") or ""
    model = get_model()
    article_embedding = model.encode(article_text, convert_to_tensor=True)
    score = util.cos_sim(claim_embedding, article_embedding).item()

    return {
        "source": article["source"],
        "title": article["title"],
        "url": article["url"],
        "similarity_score": _round_score(score),
        "status": article["status"],
        "word_count": article["word_count"],
    }


def _sort_scored_articles(scored_articles: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """
    Sorts articles by score.

    VERA Files gets a tiny bonus for ordering only, because it is the priority
    fact-checking layer. The displayed similarity score is not changed.
    """
    def ranking_score(article: Dict[str, object]) -> float:
        bonus = VERA_PRIORITY_BONUS if article["source"] == "VERA Files" else 0.0
        return float(article["similarity_score"]) + bonus

    return sorted(scored_articles, key=ranking_score, reverse=True)


def generate_verdict(claim: str, articles: List[Dict[str, object]]) -> Dict[str, object]:
    """
    Generates the Week 3 verdict from extracted articles.

    Only articles with status == "extracted" and non-empty text are scored.
    """
    extracted_articles = [
        article
        for article in articles
        if article.get("status") == "extracted" and article.get("text")
    ]

    if not extracted_articles:
        return {
            "verdict": "Not Found",
            "reason": "No readable article text was extracted from the approved sources.",
            "corroboration_count": 0,
            "primary_evidence": None,
            "supporting_sources": [],
            "similarity_thresholds": {
                "verified": VERIFIED_THRESHOLD,
                "partial": PARTIAL_THRESHOLD,
            },
        }

    model = get_model()
    claim_embedding = model.encode(claim, convert_to_tensor=True)

    scored_articles = [
        _score_article(claim_embedding, article)
        for article in extracted_articles
    ]
    ranked_articles = _sort_scored_articles(scored_articles)

    primary_evidence = ranked_articles[0]
    best_score = float(primary_evidence["similarity_score"])
    verdict = _get_verdict_label(best_score)

    supporting_sources = [
        article
        for article in ranked_articles
        if float(article["similarity_score"]) >= PARTIAL_THRESHOLD
    ]
    corroborating_source_names = {
        article["source"] for article in supporting_sources
    }

    return {
        "verdict": verdict,
        "reason": _get_reason(verdict, best_score),
        "corroboration_count": len(corroborating_source_names),
        "primary_evidence": primary_evidence,
        "supporting_sources": supporting_sources,
        "similarity_thresholds": {
            "verified": VERIFIED_THRESHOLD,
            "partial": PARTIAL_THRESHOLD,
        },
    }
