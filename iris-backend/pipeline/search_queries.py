"""
Search query helpers for claim retrieval.

These only shape what IRIS asks the search engine. They never decide whether
evidence supports a claim; retrieved text must still state the facts itself.
"""

from __future__ import annotations

import re
from typing import List, Optional

from pipeline.content_profiler import _split_segments
from pipeline.text_boundaries import quote_spans

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
# Shorter than this and a quotation is a phrase, not something an article would repeat.
QUOTE_QUERY_MIN_WORDS = 4
QUOTE_QUERY_MAX_WORDS = 30
_QUOTE_MARKS = re.compile(r"[\"\u201c\u201d\u2018\u2019]")
# A quotation is recognised by the words only it would use. The first run counted "hindi" and
# "siya" among the words of an auditor's Tagalog answer in saved case A02, and seventeen
# unrelated Tagalog pages -- SALN rules, the Dacera case, Binay -- passed as reports of it.
QUOTE_FUNCTION_WORDS = frozenset("""
    that this with from have they them their there then than what which when where while were
    been will would could should just only also about into your yours some very even because
    these those being does here said know
    hindi siya sila kami tayo kayo niya nila namin natin ninyo para kasi nang naman lang lamang
    pero kung kaya dahil ngayon yung iyon iyan dito doon diyan talaga sana pala baka wala
    mayroon meron ganun ganoon ganito kanya kanila akin atin amin inyo kaysa maging yata kapag
    habang upang bago pati lahat isang mula hanggang tungkol nasa ayon
""".split())
# Fewer than this and a quotation says too little of its own to be told apart from others.
QUOTE_MIN_DISTINCT_WORDS = 2
# Titles and generational suffixes are not how an article names someone.
_NAME_SUFFIXES = frozenset({"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"})


def distinctive_quote_words(text: str) -> set:
    """The words of a quotation that belong to it rather than to the language it is in."""
    return {word.casefold() for word in re.findall(r"[^\W\d_]{4,}", text or "")
            if word.casefold() not in QUOTE_FUNCTION_WORDS}


def speaker_surname(claim: dict) -> str:
    """The name an article would call the speaker by, or "" when the claim does not say."""
    parts = str((claim.get("attribution") or {}).get("speaker") or "").split()
    while parts and parts[-1].casefold().rstrip(",") in _NAME_SUFFIXES:
        parts.pop()
    return parts[-1].rstrip(",") if parts and parts[-1][:1].isupper() else ""


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


def _longest_quote(sentence: str) -> str:
    """The longest quotation in a sentence, without its marks or the punctuation around it."""
    best = ""
    for start, end in quote_spans(sentence):
        inner = _QUOTE_MARKS.sub(" ", sentence[start + 1:end - 1])
        inner = re.sub(r"\s+", " ", inner).strip(" ,.;:!?'")
        if len(inner.split()) > len(best.split()):
            best = inner
    return best


def verbatim_quote_query(claim: dict, original_text: str, translated_text: Optional[str] = None) -> Optional[dict]:
    """
    The quotation a quote claim rests on, as the post wrote it, ready to search for directly.

    A claim is often a translation or a paraphrase of what was said. The article that reported
    the quotation carries the speaker's own words, in the language they were spoken, so those
    are what find it. Sara Duterte's "Para kasi sa administrasyong Marcos..." turned up the
    Inquirer and Manila Bulletin reports that carry it; its English translation found neither.

    Works for any language, because the post is matched sentence by sentence rather than by
    translating back: a Tagalog quote inside an English post (held-out H15) is found as it is.

    Returns {"query", "quote", "speaker"}, or None when the claim's sentence quotes nothing
    distinctive enough, or the claim does not say who spoke.
    """
    claim_text = str(claim.get("claim_text") or claim.get("normalized_claim") or "")
    claim_words = _content_words(claim_text)
    originals = _split_segments(original_text or "")
    if not claim_words or not originals:
        return None

    translations = []
    if translated_text and translated_text != original_text:
        candidates = _split_segments(translated_text)
        if len(candidates) == len(originals):
            translations = candidates

    best_quote, best_share = "", 0.0
    for index, sentence in enumerate(originals):
        quote = _longest_quote(sentence)
        if len(quote.split()) < QUOTE_QUERY_MIN_WORDS:
            continue
        # A translated sentence is compared in both languages, so an English claim still finds
        # the Tagalog sentence it was translated from.
        compared = sentence + " " + (translations[index] if translations else "")
        share = len(claim_words & _content_words(compared)) / len(claim_words)
        if share > best_share:
            best_quote, best_share = quote, share

    if best_share < MIN_ALIGNED_OVERLAP:
        # The claim may keep the quotation itself even when no sentence of the post matches it.
        best_quote = _longest_quote(claim_text)
        if len(best_quote.split()) < QUOTE_QUERY_MIN_WORDS:
            return None

    # Without a name, a search cannot tell whose words it has found: an article that repeats
    # the quotation is only a report of it if it also names who said it.
    surname = speaker_surname(claim)
    if not surname or len(distinctive_quote_words(best_quote)) < QUOTE_MIN_DISTINCT_WORDS:
        return None

    words = best_quote.split()
    if surname.casefold() not in {word.casefold() for word in words}:
        words = [surname, *words]

    return {"query": _trim_words(" ".join(words), QUOTE_QUERY_MAX_WORDS),
            "quote": best_quote, "speaker": surname}
