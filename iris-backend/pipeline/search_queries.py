"""
Search query helpers for claim retrieval.

These only shape what IRIS asks the search engine. They never decide whether
evidence supports a claim; retrieved text must still state the facts itself.
"""

from __future__ import annotations

import re
from typing import List, Optional

from pipeline.content_profiler import _split_segments

MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
DATE_PATTERN = re.compile(
    r"\b(?P<month>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*)\.?\s+(?P<day>\d{1,2})\b",
    re.I,
)
NUMBER_PATTERN = re.compile(r"(?<![\w.])(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{2,})(?![\w])")
QUOTED_PATTERN = re.compile(r"[\"“‘']([^\"”’']{3,80})[\"”’']")
WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
MAX_ANCHORS = 4
MAX_QUOTED_TITLE_WORDS = 6
MAX_ORIGINAL_QUERY_WORDS = 30
MIN_ALIGNED_OVERLAP = 0.34


def _date_in(text: str, month: str, day: str) -> bool:
    prefix = month[:3].casefold()
    for match in DATE_PATTERN.finditer(text):
        if match.group("month")[:3].casefold() == prefix and int(match.group("day")) == int(day):
            return True
    return False


def query_anchors(claim_text: str, query: str) -> List[str]:
    """Distinctive dates, numbers and short quoted titles missing from the query."""
    anchors: List[str] = []
    folded_query = query.casefold()

    for match in DATE_PATTERN.finditer(claim_text):
        if match.group("month")[:3].casefold() not in MONTHS:
            continue
        if not _date_in(query, match.group("month"), match.group("day")):
            anchors.append(f"{match.group('month')} {match.group('day')}")

    for match in NUMBER_PATTERN.finditer(claim_text):
        number = match.group()
        # Days already covered by a date, and bare years inside dates, add nothing.
        if number in folded_query or any(number == a.split()[-1] for a in anchors):
            continue
        anchors.append(number)

    for match in QUOTED_PATTERN.finditer(claim_text):
        title = " ".join(match.group(1).strip(" ,.").split())
        if 0 < len(title.split()) <= MAX_QUOTED_TITLE_WORDS and title.casefold() not in folded_query:
            anchors.append(title)

    unique: List[str] = []
    for anchor in anchors:
        if anchor.casefold() not in {existing.casefold() for existing in unique}:
            unique.append(anchor)
    return unique[:MAX_ANCHORS]


def anchored_query(query: str, claim_text: str) -> str:
    """Appends the claim's distinctive anchors that the search query dropped."""
    query = " ".join(str(query or "").split())
    anchors = query_anchors(str(claim_text or ""), query)
    return " ".join([query, *anchors]).strip()


def attribution_search_query(speaker: Optional[str], assertion: str, max_terms: int = 7) -> str:
    """
    Speaker plus the assertion's names, numbers and key words, instead of the whole sentence.

    Long word-for-word sentences are brittle search queries, especially translations.
    The full assertion remains available to retrieval as the backup query.
    """
    from pipeline.claim_extractor import _factual_search_query

    keywords = _factual_search_query(assertion, max_terms=max_terms)
    speaker = " ".join(str(speaker or "").split())
    if speaker and speaker.casefold() not in keywords.casefold():
        keywords = f"{speaker} {keywords}"
    return keywords.strip() or " ".join(assertion.split())


def _content_words(text: str) -> set:
    return {word.casefold() for word in WORD_PATTERN.findall(text or "") if len(word) >= 3}


def _anchor_words(text: str) -> set:
    names = {word.casefold() for word in re.findall(r"\b[A-Z][\w'-]{2,}", text or "")}
    return names | set(NUMBER_PATTERN.findall(text or ""))


def _trim_words(text: str, limit: int = MAX_ORIGINAL_QUERY_WORDS) -> str:
    return " ".join(text.split()[:limit])


def original_language_query(claim_text: str, original_text: str, translated_text: str) -> Optional[str]:
    """
    Returns the original Filipino/Taglish sentence that a translated claim came from.

    Uses the profiler's sentence alignment when the original and translation
    split into the same number of sentences; otherwise matches on shared names
    and numbers. Returns None when no sentence can be identified.
    """
    original_text = str(original_text or "").strip()
    translated_text = str(translated_text or "").strip()
    if not original_text or not claim_text or original_text == translated_text:
        return None

    originals = _split_segments(original_text)
    translations = _split_segments(translated_text)
    claim_words = _content_words(claim_text)
    best_index, best_score = None, 0.0

    if originals and len(originals) == len(translations) and claim_words:
        for index, translation in enumerate(translations):
            score = len(claim_words & _content_words(translation)) / len(claim_words)
            if score > best_score:
                best_index, best_score = index, score
        if best_index is not None and best_score >= MIN_ALIGNED_OVERLAP:
            return _trim_words(originals[best_index])

    claim_anchors = _anchor_words(claim_text)
    best_index, best_score = None, 0
    for index, original in enumerate(originals):
        score = len(claim_anchors & _anchor_words(original))
        if score > best_score:
            best_index, best_score = index, score
    if best_index is not None:
        return _trim_words(originals[best_index])

    if len(original_text.split()) <= MAX_ORIGINAL_QUERY_WORDS:
        return _trim_words(original_text)
    return None
