"""
Similarity-based verdict generation for IRIS.

Week 3 uses sentence-transformers to compare the user claim against extracted
article text. No OpenAI is used here.
"""

from __future__ import annotations

from iris_trace.core import traced
from pipeline.sources import is_fact_check_source

import os
from pathlib import Path
import hashlib
import threading
from typing import Dict, List, Optional

try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:  # pragma: no cover - depends on local ML environment setup
    SentenceTransformer = None

    class _MissingSentenceTransformerUtil:
        def cos_sim(self, *_args, **_kwargs):
            raise RuntimeError("sentence-transformers is not installed.")

    util = _MissingSentenceTransformerUtil()


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VERIFIED_THRESHOLD = 0.85
PARTIAL_THRESHOLD = 0.50
VERA_PRIORITY_BONUS = 0.03
DEFAULT_MODEL_CACHE = Path(__file__).resolve().parents[1] / ".hf_cache"
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

_model: Optional[object] = None


@traced('model.semantic_load')
def get_model() -> object:
    """Loads the embedding model once, then reuses it for future requests."""
    global _model

    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed.")

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


# Reading an article is expensive; reading it again for the next claim of the same post is
# waste. Held-out post H25 spent 236 of its 329 seconds here, encoding the same articles once
# per claim, one at a time. The score of an article is exactly what it was before.
EMBEDDING_CACHE_MAX = 4000
ENCODE_BATCH = 16
_embeddings: Dict[str, object] = {}
_embeddings_guard = threading.Lock()
# Encoding is work for the processor, not the network. Several claims encoding at once on the
# same machine fight over it: one claim of held-out post H25 spent 172 seconds this way. They
# take turns instead, and whoever goes second usually finds the articles already encoded.
_encode_guard = threading.Lock()


def _embedding_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()


def article_embeddings(texts: List[str]) -> List[object]:
    """The vector for each text, encoding in one batch whatever is not already known."""
    model = get_model()
    keys = [_embedding_key(text) for text in texts]
    with _embeddings_guard:
        unknown = list(dict.fromkeys(
            text for text, key in zip(texts, keys) if text and key not in _embeddings))

    if unknown:
        with _encode_guard:
            # Another claim may have encoded these while this one waited for its turn.
            with _embeddings_guard:
                unknown = [text for text in unknown if _embedding_key(text) not in _embeddings]
            if unknown:
                encoded = model.encode(unknown, convert_to_tensor=True, batch_size=ENCODE_BATCH)
                with _embeddings_guard:
                    for text, vector in zip(unknown, encoded):
                        if len(_embeddings) >= EMBEDDING_CACHE_MAX:
                            _embeddings.pop(next(iter(_embeddings)), None)
                        _embeddings[_embedding_key(text)] = vector

    with _embeddings_guard:
        return [_embeddings.get(key) for key in keys]


def _score_article(claim_embedding, article: Dict[str, object],
                   article_embedding=None) -> Dict[str, object]:
    """Scores one extracted article against the claim."""
    article_text = article.get("text") or ""
    if article_embedding is None:
        article_embedding = article_embeddings([article_text])[0]
    score = util.cos_sim(claim_embedding, article_embedding).item() if article_embedding is not None else 0.0

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

    Fact-checking sources (VERA Files, Rappler) get a tiny bonus for ordering
    only, because they are the priority layer. The displayed similarity score is
    not changed.
    """
    def ranking_score(article: Dict[str, object]) -> float:
        bonus = VERA_PRIORITY_BONUS if is_fact_check_source(article["source"]) else 0.0
        return float(article["similarity_score"]) + bonus

    return sorted(scored_articles, key=ranking_score, reverse=True)


@traced('claim.semantic', dependency=True)
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

    try:
        model = get_model()
    except RuntimeError as error:
        return {
            "verdict": "Not Found",
            "reason": f"Semantic similarity scoring is unavailable: {error}",
            "corroboration_count": 0,
            "primary_evidence": None,
            "supporting_sources": [],
            "similarity_thresholds": {
                "verified": VERIFIED_THRESHOLD,
                "partial": PARTIAL_THRESHOLD,
            },
            "scoring_status": "missing_dependency",
        }

    claim_embedding = model.encode(claim, convert_to_tensor=True)

    embeddings = article_embeddings([article.get("text") or "" for article in extracted_articles])
    scored_articles = [
        _score_article(claim_embedding, article, embedding)
        for article, embedding in zip(extracted_articles, embeddings)
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
        "ranked_articles": [
            {"url": article["url"], "similarity_score": article["similarity_score"]}
            for article in ranked_articles
        ],
        "similarity_thresholds": {
            "verified": VERIFIED_THRESHOLD,
            "partial": PARTIAL_THRESHOLD,
        },
    }
