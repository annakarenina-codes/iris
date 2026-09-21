"""
Event-level retrieval helpers for quote-heavy IRIS posts.

Quote-heavy posts often contain very narrow claim text, such as one sentence
from a hearing transcript. Search engines are much more likely to find relevant
coverage when IRIS searches the broader event context first, then reuses that
evidence for the individual quote-derived claims.
"""

from __future__ import annotations

from iris_trace.core import traced

from collections import Counter
import re
from typing import Dict, Iterable, List, Optional


EVENT_QUERY_PRIORITY_PHRASES = [
    "Robinhood Padilla",
    "Roderick Wamil",
    "Bangsamoro Autonomous Region in Muslim Mindanao",
    "BARMM",
    "terrorism threats",
    "security threats",
    "confidential funds",
    "Audit Observation Memorandum",
    "Sara Duterte",
    "confidential agents",
    "New People's Army",
    "NPA",
    "joint circular",
    "classified",
    "evaluation",
]

EVENT_QUERY_STOPWORDS = {
    "about",
    "after",
    "already",
    "also",
    "and",
    "answered",
    "asked",
    "aware",
    "because",
    "before",
    "being",
    "but",
    "charge",
    "correct",
    "could",
    "define",
    "during",
    "ever",
    "former",
    "from",
    "furthered",
    "have",
    "identified",
    "interjection",
    "investigation",
    "judge",
    "names",
    "ones",
    "preliminary",
    "questions",
    "real",
    "regarding",
    "replied",
    "said",
    "senator",
    "state",
    "their",
    "then",
    "there",
    "these",
    "those",
    "trying",
    "used",
    "visited",
    "whether",
    "which",
    "with",
}

QUOTE_DERIVED_MARKERS = [
    "asked",
    "answered",
    "replied",
    "said",
    "stated",
    "told",
    "responded",
    "furthered",
    "defined",
    "quote",
]


# Facebook's furniture, not what a post says. A page's "READ MORE: <link>" footer and the
# "See less" control put "READ MORE", "See" and the link's slug "Sarablamesadmin" into the one
# query that finds evidence for every claim of Sara Duterte's post, crowding out the words that
# name the event. Seven of the twenty-five held-out posts carry the same footer.
_POST_CHROME = re.compile(
    r"https?://\S+|\bwww\.\S+|\bread\s+more\b\s*:?|\bsee\s+(?:less|more)\b",
    re.I,
)


def _without_post_chrome(text: str) -> str:
    return re.sub(r"\s+", " ", _POST_CHROME.sub(" ", text or "")).strip()


def _clean_markup(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", str(text or ""))
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_term(term: str) -> str:
    term = _clean_markup(term)
    term = re.sub(r"^[\"'`“”‘’]+|[\"'`“”‘’]+$", "", term)
    term = re.sub(r"\s+[,;:.!?]+$", "", term)
    return re.sub(r"\s+", " ", term).strip()


def _append_term(terms: List[str], seen: set, term: str) -> None:
    term = _normalize_term(term)
    if not term:
        return

    key = term.lower()
    if key in seen:
        return
    if any(key in existing or existing in key for existing in seen):
        return

    seen.add(key)
    terms.append(term)


def _proper_noun_phrases(text: str) -> List[str]:
    clean_text = _clean_markup(text)
    pattern = (
        r"\b(?:[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.'-]+|[A-Z]{2,})"
        r"(?:\s+(?:[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.'-]+|[A-Z]{2,}|of|the|and|in|for|to)){0,6}\b"
    )
    phrases = []

    for match in re.finditer(pattern, clean_text):
        phrase = _normalize_term(match.group(0))
        phrase = re.sub(r"\s+(?:of|the|and|in|for|to)$", "", phrase, flags=re.IGNORECASE)
        if len(phrase) <= 2:
            continue
        if phrase.split()[0].lower() in EVENT_QUERY_STOPWORDS:
            continue
        phrases.append(phrase)

    return phrases


def _topic_keywords(text: str, limit: int = 5) -> List[str]:
    words = []
    for word in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9'-]{4,}", _clean_markup(text)):
        normalized = word.lower().strip("'-.")
        if normalized in EVENT_QUERY_STOPWORDS:
            continue
        words.append(word.strip("'-."))

    counts = Counter(word.lower() for word in words)
    ranked = sorted(
        {word for word in words},
        key=lambda item: (-counts[item.lower()], text.lower().find(item.lower())),
    )
    return ranked[:limit]


@traced('event.query', dependency=False)
def build_event_search_query(
    text: str,
    translated_text: Optional[str] = None,
    claims: Optional[Iterable[Dict[str, object]]] = None,
    max_terms: int = 8,
) -> str:
    """Builds one broader query for a whole post, not one narrow claim."""
    claim_text = " ".join(
        str(claim.get("search_query") or claim.get("normalized_claim") or claim.get("claim_text") or "")
        for claim in (claims or [])
    )
    source_text = _without_post_chrome(" ".join([
        _clean_markup(translated_text or ""),
        _clean_markup(text or ""),
        _clean_markup(claim_text),
    ]))
    normalized = source_text.lower()
    terms: List[str] = []
    seen = set()

    for phrase in EVENT_QUERY_PRIORITY_PHRASES:
        if phrase.lower() in normalized:
            _append_term(terms, seen, phrase)
        if len(terms) >= max_terms:
            return " ".join(terms[:max_terms])

    for phrase in _proper_noun_phrases(source_text):
        _append_term(terms, seen, phrase)
        if len(terms) >= max_terms:
            return " ".join(terms[:max_terms])

    for word in _topic_keywords(source_text):
        _append_term(terms, seen, word)
        if len(terms) >= max_terms:
            break

    return " ".join(terms[:max_terms]).strip()


def _has_quote_signal(text: str) -> bool:
    normalized = _clean_markup(text).lower()
    return (
        bool(re.search(r"[\"'“”][^\"'“”]{3,260}[\"'“”]", text))
        or any(re.search(rf"\b{re.escape(marker)}\b", normalized) for marker in QUOTE_DERIVED_MARKERS)
    )


def _quote_segments(content_profile: Dict[str, object]) -> List[str]:
    segments = []
    for segment in content_profile.get("segments") or []:
        scores = segment.get("scores") or {}
        reasons = segment.get("reason_codes") or []
        if float(scores.get("quote", 0.0) or 0.0) >= 0.45 or "quote_context_needed" in reasons:
            segments.append(str(segment.get("text") or ""))

    return segments


def _meaningful_terms(text: str) -> set:
    return {
        term
        for term in re.findall(r"[a-z0-9]+", _clean_markup(text).lower())
        if len(term) >= 4 and term not in EVENT_QUERY_STOPWORDS
    }


def is_quote_derived_claim(claim: Dict[str, object], content_profile: Dict[str, object]) -> bool:
    """Flags claims that should be checked against event-level evidence."""
    if not content_profile.get("contains_quote"):
        return False

    if claim.get("is_quote_derived") is True:
        return True

    if claim.get("claim_type") == "attributed_statement":
        return True

    claim_text = " ".join([
        str(claim.get("claim_text") or ""),
        str(claim.get("normalized_claim") or ""),
        str(claim.get("search_query") or ""),
    ])
    if _has_quote_signal(claim_text):
        return True

    claim_terms = _meaningful_terms(claim_text)
    for segment in _quote_segments(content_profile):
        segment_terms = _meaningful_terms(segment)
        if len(claim_terms.intersection(segment_terms)) >= 3:
            return True

    return False


@traced('claims.quote_mark', dependency=False)
def mark_quote_derived_claims(
    claims: Iterable[Dict[str, object]],
    content_profile: Dict[str, object],
) -> List[Dict[str, object]]:
    """Returns copied claims with a stable is_quote_derived flag."""
    marked = []
    for claim in claims:
        claim_copy = dict(claim)
        claim_copy["is_quote_derived"] = is_quote_derived_claim(claim_copy, content_profile)
        marked.append(claim_copy)

    return marked
