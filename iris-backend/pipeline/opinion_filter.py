"""
Rule-based opinion detection for IRIS.

This module catches obvious opinions before the backend spends API calls on
searching or AI processing. It is intentionally conservative: if the text only
slightly looks like an opinion, the system should continue verification later.
"""

from __future__ import annotations

import re
from typing import Dict, List


OPINION_PHRASES = [
    "sa tingin ko",
    "para sa akin",
    "palagay ko",
    "akala ko",
    "opinyon ko",
    "in my opinion",
    "i think",
    "i believe",
    "i feel",
    "for me",
    "personally",
]

OPINION_WORDS = [
    "dapat",
    "masama",
    "mabuti",
    "maganda",
    "pangit",
    "best",
    "worst",
    "better",
    "should",
    "must",
]


def _normalize(text: str) -> str:
    """Lowercase text and make spacing predictable for keyword matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def is_opinion(text: str) -> Dict[str, object]:
    """
    Checks whether text is clearly an opinion.

    Returns a dictionary so app.py can explain why the text was classified as an
    opinion instead of only returning True or False.
    """
    normalized = _normalize(text)

    matched_phrases: List[str] = [
        phrase for phrase in OPINION_PHRASES if phrase in normalized
    ]

    matched_words: List[str] = [
        word
        for word in OPINION_WORDS
        if re.search(rf"\b{re.escape(word)}\b", normalized)
    ]

    is_clear_opinion = bool(matched_phrases) or len(matched_words) >= 2

    return {
        "is_opinion": is_clear_opinion,
        "matched_phrases": matched_phrases,
        "matched_words": matched_words,
    }
