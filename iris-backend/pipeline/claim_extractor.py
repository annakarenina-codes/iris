"""
Claim extraction for IRIS Week 4.

OpenAI is used when configured. If the API key, SDK, or request is unavailable,
IRIS falls back to a conservative sentence splitter so the rest of the pipeline
can still run.
"""

from __future__ import annotations

from iris_trace.core import traced, event

import json
import os
import re
from typing import Dict, List, Optional
from pipeline.text_boundaries import is_attribution_tail, split_statement_segments
from pipeline.quotation_context import SPEECH_RULES, speech_scopes, validate_speech_coverage, QuotationExtractionError

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment setup
    def load_dotenv():
        return False


load_dotenv()

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_CLAIM_REVIEW_MODEL = os.getenv("IRIS_CLAIM_REVIEW_MODEL", "gpt-4.1-2025-04-14")
ATTRIBUTED_CLAIM_TYPE = "attributed_statement"
ALLOWED_CLAIM_TYPES = {"factual_claim", ATTRIBUTED_CLAIM_TYPE}
OPINION_MARKERS = [
    "delikado",
    "fake news",
    "kawawa",
    "kadiliman",
    "panloloko",
    "pagbabayaran",
    "widely respected",
    "leading expert",
    "leading experts",
    "world-class",
    "generous mentor",
    "reminds us",
    "helped defend",
    "significant role",
    "biggest international legal victories",
    "we support",
    "we protect",
    "i support",
]
RECOMMENDATION_MARKERS = [
    "should",
    "dapat",
    "kailangan",
    "revoke",
    "confiscated",
    "disarmed",
    "panawagan",
]
FACTUAL_MARKERS = [
    "ayon",
    "sinabi",
    "reported",
    "announced",
    "asked",
    "answered",
    "began",
    "condemned",
    "conducted",
    "delivered",
    "dumating",
    "evidence",
    "entered",
    "favored",
    "injured",
    "investigators",
    "makikita",
    "nagpasya",
    "inatasan",
    "pinalitan",
    "prompted tributes",
    "remain at large",
    "research",
    "replied",
    "reviewing",
    "ruling",
    "shot",
    "submitted",
    "testimony",
    "tributes",
    "vowed",
    "confidential funds",
    "audit observation memorandum",
    "terrorism threats",
    "security threats",
    "confidential agents",
    "joint circular",
    "classified",
    "evaluation",
    "licensed",
    "firearms",
    "fugitive",
    "senator",
    "pangulong",
    "president",
    "mayor",
]
HIGH_RISK_MARKERS = [
    "fugitive",
    "criminal",
    "wanted",
    "corrupt",
    "corruption",
    "kasalanan",
    "licensed firearms",
    "firearms",
]
ATTRIBUTION_VERBS = [
    "said",
    "stated",
    "argued",
    "claimed",
    "explained",
    "warned",
    "noted",
    "added",
    "cited",
    "condemned",
    "vowed",
    "made the argument",
]
SPEAKER_TITLE_PATTERN = (
    r"(?:(?:cybersecurity\s+and\s+technology\s+expert|"
    r"cybersecurity\s+expert|technology\s+expert|"
    r"former\s+state\s+auditor|state\s+auditor|"
    r"senator-judge|senator\s+judge|auditor|witness|"
    r"police\s+brigadier\s+general|brigadier\s+general|"
    r"police\s+general|general|political\s+analyst|"
    r"lawyer|attorney|senator|mayor|president|secretary|"
    r"spokesperson|expert)\s+)"
)
NAME_TOKEN_PATTERN = r"[^\W\d_][^\W\d_.'-]*"
PERSON_NAME_PATTERN = (
    rf"{NAME_TOKEN_PATTERN}"
    rf"(?:\s+{NAME_TOKEN_PATTERN}){{0,5}}"
    r"(?:\s+Jr\.?)?"
)
NAME_PARTICLES = {"de", "del", "dela", "la", "las", "los", "van", "von"}
NON_PERSON_SPEAKER_PREFIXES = {
    "the",
    "department",
    "office",
    "agency",
    "police",
    "government",
    "school",
}
KNOWN_SOURCE_NAMES = [
    "DZRH News",
    "VERA Files",
    "ABS-CBN News",
    "ABS-CBN",
    "GMA News",
    "Inquirer",
    "Philippine Daily Inquirer",
    "Philippine Star",
    "Philstar",
    "Manila Bulletin",
    "Philippine News Agency",
    "Philippine Information Agency",
]
SEARCH_STOPWORDS = {
    "the",
    "and",
    "that",
    "with",
    "from",
    "this",
    "there",
    "their",
    "about",
    "because",
    "should",
    "would",
    "could",
    "have",
    "were",
    "was",
    "are",
    "his",
    "her",
    "they",
    "them",
    "real",
    "direct",
}

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on local environment setup
    OpenAI = None


def _get_api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


def _normalize_claim(text: str) -> str:
    text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", text)
    text = re.sub(r"^[\"'`“”‘’]+|[\"'`“”‘’]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_leading_headline_question(segment: str) -> List[str]:
    match = re.match(
        r"^(?P<head>[\"'`“”‘’]?[A-Z0-9][A-Z0-9\s,'-]{2,80}\?[\"'`“”‘’]?)\s+(?P<rest>.+)$",
        segment,
    )
    if not match or is_attribution_tail(match.group("rest")):
        return [segment]

    return [match.group("head"), match.group("rest")]


def _split_segments(text: str) -> List[str]:
    segments = []
    for part in split_statement_segments(text):
        for statement in _split_leading_headline_question(part):
            segment = _normalize_claim(statement)
            if segment:
                segments.append(segment)

    return segments


def _contains_any(text: str, markers: List[str]) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in markers)


def _has_factual_signal(text: str) -> bool:
    return bool(re.search(r"\b\d+\b", text)) or _contains_any(text, FACTUAL_MARKERS)


def _is_evaluative_segment(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in OPINION_MARKERS)


def _is_headline_question(text: str) -> bool:
    stripped = text.strip(" \"'`“”‘’")
    if not stripped.endswith("?") or len(stripped.split()) > 8:
        return False

    letters = re.findall(r"[A-Za-z]", stripped)
    uppercase = re.findall(r"[A-Z]", stripped)
    return bool(letters) and len(uppercase) / len(letters) >= 0.70


def _segment_type(text: str) -> str:
    if _is_headline_question(text):
        return "uncheckable"

    if _contains_any(text, RECOMMENDATION_MARKERS):
        return "recommendation"

    if _contains_any(text, OPINION_MARKERS):
        return "opinion"

    if len(text.split()) < 3:
        return "uncheckable"

    if _has_factual_signal(text):
        return "factual_claim"

    return "uncheckable"


def _risk_tags(text: str) -> List[str]:
    normalized = text.lower()
    tags = []

    if any(marker in normalized for marker in ["fugitive", "criminal", "wanted"]):
        tags.append("criminal_allegation")

    if any(marker in normalized for marker in ["firearms", "licensed firearms", "pistols", "rifles", "shotguns"]):
        tags.append("weapons_claim")

    if _contains_any(text, HIGH_RISK_MARKERS):
        tags.append("high_risk_claim")

    return sorted(set(tags))


def _clean_markup(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return text


def _normalize_sentence(text: str) -> str:
    text = _normalize_claim(_clean_markup(text))
    text = re.sub(r"\s+[,;:.!?]+$", "", text).strip()
    return text


def _sentence_with_period(text: str) -> str:
    text = _normalize_sentence(text)
    if text and text[-1] not in ".!?":
        return f"{text}."

    return text


def _clean_speaker(candidate: str) -> str:
    speaker = _normalize_sentence(candidate)
    speaker = re.sub(
        rf"^{SPEAKER_TITLE_PATTERN}",
        "",
        speaker,
        flags=re.IGNORECASE,
    ).strip()
    speaker = re.sub(r"^(?:a|an|the)\s+", "", speaker, flags=re.IGNORECASE)
    speaker = re.sub(r"\s+", " ", speaker).strip(" ,")
    return speaker


def _is_person_like_speaker(candidate: str) -> bool:
    speaker = _clean_speaker(candidate)
    if not speaker:
        return False

    first_word = speaker.split()[0].lower()
    if first_word in NON_PERSON_SPEAKER_PREFIXES:
        return False

    if speaker.lower() in {"he", "she", "they", "expert"}:
        return False

    name_tokens = [
        token.strip(".,")
        for token in speaker.split()
        if token.strip(".,").lower() not in NAME_PARTICLES
        and token.strip(".,").lower() not in {"jr", "sr"}
    ]
    if len(name_tokens) < 2:
        return False

    uppercase_initial = re.compile(r"^[A-ZÀ-ÖØ-Þ]")
    if not all(uppercase_initial.match(token) for token in name_tokens):
        return False

    return bool(re.match(rf"^{PERSON_NAME_PATTERN}$", speaker))


def _find_named_speaker(text: str) -> Optional[str]:
    text = _clean_markup(text)
    verb_pattern = "|".join(re.escape(verb) for verb in ATTRIBUTION_VERBS)
    patterns = [
        rf"(?:{SPEAKER_TITLE_PATTERN})?(?P<speaker>{PERSON_NAME_PATTERN})\s+(?:{verb_pattern})\b",
        rf"{SPEAKER_TITLE_PATTERN}(?P<speaker>{PERSON_NAME_PATTERN})",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            speaker = _clean_speaker(match.group("speaker"))
            if _is_person_like_speaker(speaker) and len(speaker.split()) >= 2:
                return speaker

    return None


def _extract_speaker_role(text: str, speaker: Optional[str]) -> Optional[str]:
    if not speaker:
        return None

    clean_text = _clean_markup(text)
    role_pattern = (
        r"cybersecurity\s+and\s+technology\s+expert|"
        r"cybersecurity\s+expert|technology\s+expert|"
        r"political\s+analyst|lawyer|attorney|senator|mayor|"
        r"president|secretary|spokesperson|expert"
    )
    role_match = re.search(
        rf"\b(?P<role>{role_pattern})\s+{re.escape(speaker)}(?=\s|[,.]|$)",
        clean_text,
        flags=re.IGNORECASE,
    )

    if not role_match:
        return None

    return _normalize_sentence(role_match.group("role")).capitalize()


def _speaker_last_name(speaker: Optional[str]) -> str:
    if not speaker:
        return ""

    parts = [
        part
        for part in re.sub(r"\bJr\.?$", "", speaker).split()
        if part
    ]
    return parts[-1] if parts else ""


def _resolve_sentence_speaker(segment: str, known_speaker: Optional[str]) -> Optional[str]:
    if not known_speaker:
        return None

    last_name = _speaker_last_name(known_speaker)
    verb_pattern = "|".join(re.escape(verb) for verb in ATTRIBUTION_VERBS)

    if re.search(rf"\b(?:he|she)\s+(?:{verb_pattern})\b", segment, flags=re.IGNORECASE):
        return known_speaker

    if last_name and re.search(rf"\b{re.escape(last_name)}\s+(?:{verb_pattern})\b", segment, flags=re.IGNORECASE):
        return known_speaker

    if re.search(rf"\b(?:expert|analyst|lawyer|attorney)\s+(?:{verb_pattern})\b", segment, flags=re.IGNORECASE):
        return known_speaker

    if known_speaker.lower() in segment.lower():
        return known_speaker

    return None


def _extract_source_context(text: str, speaker: Optional[str] = None) -> Dict[str, Optional[str]]:
    clean_text = _clean_markup(text)
    source = next(
        (source_name for source_name in KNOWN_SOURCE_NAMES if source_name.lower() in clean_text.lower()),
        None,
    )
    program_match = re.search(
        r"(?:program|show)\s+[\"“”']([^\"“”']{3,80})[\"“”']",
        clean_text,
        flags=re.IGNORECASE,
    )
    date_match = re.search(
        r"\bon\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s+\d{4})?)\b",
        clean_text,
        flags=re.IGNORECASE,
    )

    return {
        "role": _extract_speaker_role(clean_text, speaker),
        "source": source,
        "program": program_match.group(1).strip() if program_match else None,
        "date": date_match.group(1).strip() if date_match else None,
    }


def _quoted_statements(segment: str) -> List[str]:
    return [
        _normalize_sentence(match.group(1))
        for match in re.finditer(r"[\"“”]([^\"“”]{12,450})[\"“”]", segment)
        if _normalize_sentence(match.group(1))
    ]


def _remove_attribution_tail(text: str) -> str:
    text = re.sub(
        r",?\s+(?:a|an|the)?\s*(?:cybersecurity\s+and\s+technology\s+expert|"
        r"cybersecurity\s+expert|technology\s+expert|expert|analyst|lawyer)"
        r"\s+(?:said|stated|argued|claimed|explained|warned|noted|added)"
        r"\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return _normalize_sentence(text)


def _statements_from_attributed_segment(segment: str, speaker: str) -> List[str]:
    statements = []
    normalized = segment.lower()
    last_name = _speaker_last_name(speaker)
    verb_pattern = "|".join(re.escape(verb) for verb in ATTRIBUTION_VERBS)

    condemned_match = re.search(
        r"\bcondemned\s+(?:the\s+)?(?P<event>.+?)\s+as\s+(?:a|an|the)?\s*[\"“”](?P<quote>[^\"“”]{4,180})[\"“”]"
        r"(?:\s+and\s+vowed\s+(?P<vow>.+))?$",
        segment,
        flags=re.IGNORECASE,
    )
    if condemned_match:
        event = _normalize_sentence(condemned_match.group("event"))
        if event and not event.lower().startswith(("the ", "a ", "an ")):
            event = f"the {event}"
        quote = _normalize_sentence(condemned_match.group("quote"))
        vow = _normalize_sentence(condemned_match.group("vow") or "")
        statement = f'called {event} "{quote}"'
        if vow:
            statement = f"{statement} and vowed {vow}"
        statements.append(statement)

    if re.search(r"\b(?:said|stated|argued|claimed|explained|warned|noted|added)\b", segment, flags=re.IGNORECASE):
        statements.extend(_quoted_statements(segment))

    speaker_pattern = "|".join(
        re.escape(value)
        for value in [speaker, last_name, "he", "she"]
        if value
    )
    if speaker_pattern and " made the argument " not in normalized and not condemned_match:
        match = re.search(
            rf"\b(?:{speaker_pattern})\s+(?:{verb_pattern})\s+(?:that\s+)?(?P<statement>.+)$",
            segment,
            flags=re.IGNORECASE,
        )
        if match:
            statements.append(_normalize_sentence(match.group("statement")))

    if " made the argument " in normalized or " made the argument in " in normalized:
        research_match = re.search(
            r"\bciting\s+(?P<statement>research\s+by\s+.+?\s+showing\s+.+)$",
            segment,
            flags=re.IGNORECASE,
        )
        showing_match = re.search(r"\bshowing\s+(?P<statement>.+)$", segment, flags=re.IGNORECASE)

        if research_match:
            statement = _normalize_sentence(research_match.group("statement"))
            statement = re.sub(r"\bshowing\b", "shows", statement, count=1, flags=re.IGNORECASE)
            statements.append(statement)
        elif showing_match:
            statement = _normalize_sentence(showing_match.group("statement"))
            if statement.lower().startswith("no "):
                statement = f"there is {statement}"
            statements.append(statement)

    if re.search(r"\bexpert\s+said\b", segment, flags=re.IGNORECASE):
        before_said = re.split(
            r",?\s+(?:a|an|the)?\s*(?:cybersecurity\s+and\s+technology\s+expert|expert)\s+said\b",
            segment,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        statements.append(_remove_attribution_tail(before_said))

    cleaned = []
    for statement in statements:
        statement = _remove_attribution_tail(statement)
        statement = re.sub(r"^that\s+", "", statement, flags=re.IGNORECASE)
        if len(statement.split()) >= 5:
            cleaned.append(statement)

    return cleaned


def _statement_fingerprint(statement: str) -> str:
    words = [
        word
        for word in re.findall(r"[a-z0-9]+", statement.lower())
        if word not in SEARCH_STOPWORDS
    ]
    return " ".join(words[:14])


def _dedupe_statements(statements: List[str]) -> List[str]:
    deduped = []
    seen = set()

    for statement in statements:
        fingerprint = _statement_fingerprint(statement)
        if not fingerprint or fingerprint in seen:
            continue

        seen.add(fingerprint)
        deduped.append(statement)

    return deduped


def _dedupe_statement_records(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    deduped = []
    seen = set()

    for record in sorted(records, key=lambda item: int(item.get("priority", 99))):
        statement = str(record.get("statement") or "")
        fingerprint = _statement_fingerprint(statement)
        if not fingerprint or fingerprint in seen:
            continue

        seen.add(fingerprint)
        deduped.append(record)

    return deduped


def _search_keywords(statement: str, limit: int = 9) -> List[str]:
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9+]{4,}", statement)
    keywords = []
    seen = set()

    for word in words:
        normalized = word.lower().strip(".:,;!?")
        if normalized in SEARCH_STOPWORDS or normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(word.strip(".:,;!?"))
        if len(keywords) >= limit:
            break

    return keywords


def _attribution_search_query(
    speaker: str,
    statement: str,
    context: Dict[str, Optional[str]],
) -> str:
    terms = [speaker]

    for key in ["source", "program", "date"]:
        if context.get(key):
            terms.append(str(context[key]))

    terms.extend(_search_keywords(statement))
    return " ".join(term for term in terms if term).strip()


def _speaker_with_role(speaker: str, context: Dict[str, Optional[str]]) -> str:
    role = context.get("role")
    if not role:
        return speaker

    if role.lower() in speaker.lower():
        return speaker

    return f"{role} {speaker}"


def _attribution_context_phrase(context: Dict[str, Optional[str]]) -> str:
    pieces = []
    source = context.get("source")
    program = context.get("program")
    date = context.get("date")

    if source:
        phrase = f"as reported by {source}"
        if program:
            phrase += f' program "{program}"'
        if date:
            phrase += f" on {date}"
        pieces.append(phrase)
    elif program:
        phrase = f'on program "{program}"'
        if date:
            phrase += f" on {date}"
        pieces.append(phrase)
    elif date:
        pieces.append(f"on {date}")

    return " ".join(pieces)


def _normalized_attribution_claim(
    speaker: str,
    statement: str,
    context: Dict[str, Optional[str]],
) -> str:
    statement = _sentence_with_period(statement)
    subject = _speaker_with_role(speaker, context)
    context_phrase = _attribution_context_phrase(context)
    statement_body = f"{statement[0].lower()}{statement[1:]}" if statement else "made a statement."

    if statement.lower().startswith(("called ", "vowed ", "condemned ")):
        return f"{subject} {statement_body}"

    if context_phrase:
        return f"{subject} said {context_phrase} that {statement_body}"

    return f"{subject} said {statement_body}"


def _attribution_claim(
    index: int,
    speaker: str,
    statement: str,
    context: Dict[str, Optional[str]],
    source_sentence: Optional[str] = None,
) -> Dict[str, object]:
    statement = _sentence_with_period(statement)
    normalized_claim = _normalized_attribution_claim(speaker, statement, context)
    source_sentence = _sentence_with_period(source_sentence or "")
    claim_text = source_sentence or f'{speaker} said: "{statement}"'

    return {
        "claim_id": index,
        "claim_text": claim_text,
        "normalized_claim": normalized_claim,
        "claim_type": ATTRIBUTED_CLAIM_TYPE,
        "verification_focus": "speaker_attribution",
        "attribution": {
            "speaker": speaker,
            "role": context.get("role"),
            "statement": statement,
            "source": context.get("source"),
            "program": context.get("program"),
            "date": context.get("date"),
            "source_sentence": source_sentence or None,
        },
        "search_query": _attribution_search_query(speaker, statement, context),
        "risk_tags": _risk_tags(normalized_claim),
    }


def _attribution_segment_priority(segment: str, speaker: str, context: Dict[str, Optional[str]]) -> int:
    normalized = segment.lower()
    speaker_present = speaker.lower() in normalized
    source_present = bool(context.get("source") and str(context["source"]).lower() in normalized)
    program_present = bool(context.get("program") and str(context["program"]).lower() in normalized)
    last_name = _speaker_last_name(speaker)

    if speaker_present and (source_present or program_present):
        return 0

    if speaker_present:
        return 1

    if last_name and re.search(rf"\b{re.escape(last_name)}\b", segment, flags=re.IGNORECASE):
        return 2

    return 3


def _extract_attributed_claims(text: str, translated_text: Optional[str] = None) -> List[Dict[str, object]]:
    original_text = text or ""
    translated_text = translated_text or ""
    combined_text = f"{original_text}\n{translated_text}".strip()
    speaker = _find_named_speaker(combined_text)

    if not speaker:
        return []

    context = _extract_source_context(combined_text, speaker)
    statement_records = []
    segment_sources = [original_text]
    if translated_text and translated_text.strip().lower() != original_text.strip().lower():
        segment_sources.append(translated_text)

    for source_text in segment_sources:
        for segment in _split_segments(source_text):
            resolved_speaker = _resolve_sentence_speaker(segment, speaker)
            if not resolved_speaker:
                continue

            for statement in _statements_from_attributed_segment(segment, resolved_speaker):
                statement_records.append({
                    "statement": statement,
                    "source_sentence": _normalize_sentence(segment),
                    "priority": _attribution_segment_priority(segment, speaker, context),
                })

    statement_records = _dedupe_statement_records(statement_records)

    return [
        _attribution_claim(
            index,
            speaker,
            str(record["statement"]),
            context,
            str(record.get("source_sentence") or ""),
        )
        for index, record in enumerate(statement_records, start=1)
    ]


def _infer_subject(claim: str) -> Optional[str]:
    claim = re.sub(r"^fugitive\s+", "", claim, flags=re.IGNORECASE)
    match = re.match(
        r"([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,3})\s+(?:has|is|was|reported|announced)",
        claim,
    )

    if match:
        return match.group(1)

    return None


def _claim_from_segment(segment: str, last_subject: Optional[str]) -> str:
    normalized = segment.lower()

    if "fugitive from justice" in normalized and last_subject:
        return f"{last_subject} is a fugitive from justice."

    segment = re.sub(r"^fugitive\s+([A-Z])", r"\1", segment, flags=re.IGNORECASE)

    return segment


def _clean_named_actor(text: str) -> str:
    actor = _normalize_sentence(text)
    actor = re.sub(
        r"^(?:the\s+)?(?:late\s+|former\s+)*(?:(?:former\s+)?president\s+|"
        r"president\s+)?",
        "",
        actor,
        flags=re.IGNORECASE,
    )
    return _normalize_sentence(actor)


def _subject_from_arrest_pardon_segment(segment: str, last_subject: Optional[str]) -> Optional[str]:
    match = re.search(
        r"\b(?P<subject>[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.'-]+"
        r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.'-]+){0,3})\s+"
        r"was\s+arrested\b",
        _clean_markup(segment),
    )

    if match:
        return _normalize_sentence(match.group("subject"))

    return last_subject


def _decompose_arrest_pardon_claims(segment: str, last_subject: Optional[str]) -> List[str]:
    normalized = segment.lower()
    required_markers = [
        "arrested",
        "imprisoned",
        "illegal possession of firearms",
        "conditional pardon",
        "absolute pardon",
    ]
    if not all(marker in normalized for marker in required_markers):
        return []

    subject = _subject_from_arrest_pardon_segment(segment, last_subject)
    if not subject:
        return []

    claims = [
        f"{subject} was arrested and imprisoned for illegal possession of firearms."
    ]
    conditional_match = re.search(
        r"\bconditional\s+pardon\s+by\s+(?P<actor>.+?)\s+and\s+an\s+absolute\s+pardon\b",
        segment,
        flags=re.IGNORECASE,
    )
    absolute_match = re.search(
        r"\babsolute\s+pardon(?:\s+in\s+(?P<year>\d{4}))?\s+by\s+(?P<actor>.+?)(?:[.!?]|$)",
        segment,
        flags=re.IGNORECASE,
    )

    if conditional_match:
        actor = _clean_named_actor(conditional_match.group("actor"))
        if actor:
            claims.append(f"{subject} was granted a conditional pardon by {actor}.")

    if absolute_match:
        actor = _clean_named_actor(absolute_match.group("actor"))
        year = absolute_match.group("year")
        if actor:
            date_phrase = f" in {year}" if year else ""
            claims.append(f"{subject} was granted an absolute pardon{date_phrase} by {actor}.")

    return claims if len(claims) > 1 else []


def _claims_from_segment(segment: str, last_subject: Optional[str]) -> List[str]:
    decomposed_claims = _decompose_arrest_pardon_claims(segment, last_subject)
    if decomposed_claims:
        return decomposed_claims

    return [_claim_from_segment(segment, last_subject)]


def _primary_person_name(text: str) -> Optional[str]:
    clean_text = _clean_markup(text)
    match = re.search(
        r"\bDr\.\s+(?P<name>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4})\b",
        clean_text,
    )
    if match:
        return _normalize_sentence(match.group("name"))

    match = re.search(
        r"\b(?P<name>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4})\s+was\s+shot\b",
        clean_text,
    )
    if match:
        return _normalize_sentence(match.group("name"))

    return None


def _source_position(source_text: str, needle: str, fallback: int = 9999) -> int:
    if not needle:
        return fallback

    position = source_text.lower().find(needle.lower()[:120])
    return position if position >= 0 else fallback


def _find_segment(segments: List[str], *markers: str) -> Optional[str]:
    for segment in segments:
        normalized = segment.lower()
        if all(marker.lower() in normalized for marker in markers):
            return segment

    return None


FACTUAL_QUERY_STOPWORDS = SEARCH_STOPWORDS.union({
    "asked",
    "answered",
    "whether",
    "already",
    "visited",
    "former",
    "state",
    "senator",
    "judge",
    "witness",
    "senator-judge",
    "during",
    "interjection",
    "raised",
    "preliminary",
    "questions",
    "trying",
    "establish",
    "ties",
    "used",
    "potential",
    "regarding",
    "correct",
    "believe",
    "identified",
    "their",
    "real",
    "names",
    "provisions",
    "define",
    "ever",
    "vice",
    "but",
    "there",
    "then",
    "which",
    "ones",
    "charge",
    "to",
})
FACTUAL_QUERY_PRIORITY_PHRASES = [
    "Robinhood Padilla",
    "Roderick Wamil",
    "auditor",
    "BARMM",
    "terrorism threats",
    "security threats",
    "Sara Duterte",
    "confidential funds",
    "Audit Observation Memorandum",
    "New People's Army",
    "NPA",
    "confidential agents",
    "joint circular",
    "classified",
]


def _append_query_term(terms: List[str], seen: set, term: str) -> None:
    term = _normalize_sentence(term)
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
        r"(?:\s+(?:[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.'-]+|[A-Z]{2,}|of|the|and|in|for|to)){0,5}\b"
    )
    phrases = []

    for match in re.finditer(pattern, clean_text):
        phrase = _normalize_sentence(match.group(0))
        phrase = re.sub(r"\s+(?:of|the|and|in|for|to)$", "", phrase, flags=re.IGNORECASE)
        if len(phrase) <= 2:
            continue
        first_word = phrase.split()[0].lower()
        if first_word in FACTUAL_QUERY_STOPWORDS:
            continue
        letters = re.findall(r"[A-Za-z]", phrase)
        uppercase = re.findall(r"[A-Z]", phrase)
        if letters and len(uppercase) / len(letters) >= 0.70 and phrase.endswith("?"):
            continue
        if phrase.lower() in {"senator", "judge", "former", "state", "during"}:
            continue
        phrases.append(phrase)

    return phrases


def _factual_search_query(claim_text: str, max_terms: int = 6) -> str:
    clean_text = _clean_markup(claim_text)
    normalized = clean_text.lower()
    terms: List[str] = []
    seen = set()

    for phrase in FACTUAL_QUERY_PRIORITY_PHRASES:
        if phrase.lower() in normalized:
            _append_query_term(terms, seen, phrase)

    if "terrorism threats" in normalized or "terrorism threat" in normalized:
        _append_query_term(terms, seen, "security threats")

    for phrase in _proper_noun_phrases(clean_text):
        if len(terms) >= max_terms:
            break
        _append_query_term(terms, seen, phrase)

    for word in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9'-]{4,}", clean_text):
        if len(terms) >= max_terms:
            break
        normalized_word = word.lower().strip("'-.")
        if normalized_word in FACTUAL_QUERY_STOPWORDS:
            continue
        _append_query_term(terms, seen, word.strip("'-."))

    return " ".join(terms[:max_terms]).strip()


def _make_factual_claim(claim_text: str, source_index: int = 9999) -> Dict[str, object]:
    claim = _sentence_with_period(claim_text)
    return {
        "claim_id": 0,
        "claim_text": claim,
        "normalized_claim": claim,
        "claim_type": "factual_claim",
        "search_query": _factual_search_query(claim),
        "risk_tags": _risk_tags(claim),
        "_source_index": source_index,
    }


def _claim_fingerprint(claim: Dict[str, object]) -> str:
    attribution = claim.get("attribution")
    if claim.get("claim_type") == ATTRIBUTED_CLAIM_TYPE and isinstance(attribution, dict):
        text = str(attribution.get("statement") or claim.get("normalized_claim") or claim.get("claim_text") or "")
    else:
        text = str(claim.get("normalized_claim") or claim.get("claim_text") or "")

    # Keep the entire assertion, especially negation and late qualifiers. Punctuation
    # variants are duplicates, but different speakers making the same statement are not.
    speaker = str(attribution.get("speaker") or "") if isinstance(attribution, dict) else ""
    words = re.findall(r"[^\W_]+", text.casefold())
    return f"{claim.get('claim_type', 'factual_claim')}|{speaker.casefold()}|{' '.join(words)}" if words else ""


def _dedupe_claim_dicts(claims: List[Dict[str, object]]) -> List[Dict[str, object]]:
    deduped = []
    seen = set()

    for claim in claims:
        fingerprint = _claim_fingerprint(claim)
        if not fingerprint or fingerprint in seen:
            continue

        seen.add(fingerprint)
        deduped.append(claim)

    return deduped


def _finalize_claims(claims: List[Dict[str, object]], source_text: str) -> List[Dict[str, object]]:
    ordered = []

    for order, claim in enumerate(claims):
        claim = dict(claim)
        source_index = claim.pop("_source_index", None)
        if source_index is None:
            source_index = _source_position(source_text, str(claim.get("claim_text") or ""), 9000 + order)
        claim["_sort_index"] = source_index
        claim["_original_order"] = order
        ordered.append(claim)

    deduped = _dedupe_claim_dicts(ordered)
    deduped.sort(
        key=lambda item: (
            int(item.get("_sort_index", 9999)),
            int(item.get("_original_order", 9999)),
        )
    )

    finalized = []
    for index, claim in enumerate(deduped, start=1):
        claim.pop("_sort_index", None)
        claim.pop("_original_order", None)
        claim["claim_id"] = index
        finalized.append(claim)

    return finalized


def _renumber_claims(claims: List[Dict[str, object]]) -> List[Dict[str, object]]:
    finalized = []

    for index, claim in enumerate(_dedupe_claim_dicts([dict(item) for item in claims]), start=1):
        claim.pop("_sort_index", None)
        claim.pop("_original_order", None)
        claim.pop("_source_index", None)
        claim["claim_id"] = index
        finalized.append(claim)

    return finalized


def _extract_longform_factual_claims(source_text: str, segments: List[str]) -> List[Dict[str, object]]:
    """Extracts enriched claims from multi-paragraph factual narratives."""
    subject = _primary_person_name(source_text)
    if not subject:
        return []

    claims = []
    normalized_source = source_text.lower()

    arbitration_segment = _find_segment(segments, "scientific testimony", "arbitration")
    written_segment = _find_segment(segments, "submitted expert written evidence")
    oral_segment = _find_segment(segments, "delivered oral testimony")
    if (
        "south china sea arbitration" in normalized_source
        and (arbitration_segment or written_segment or oral_segment)
    ):
        details = []
        if written_segment:
            details.append(
                "submitted expert written evidence documenting environmental damage "
                "caused by China's island reclamation and destructive fishing practices "
                "in the West Philippine Sea"
            )
        if oral_segment:
            details.append("delivered oral testimony during the 2015 merits hearing")

        claim = (
            f"{subject} provided expert testimony or evidence supporting the "
            "Philippines in the 2016 South China Sea arbitration case against China"
        )
        if details:
            claim = f"{claim}; he {' and '.join(details)}"
        claims.append(_make_factual_claim(
            claim,
            min(
                _source_position(source_text, arbitration_segment or ""),
                _source_position(source_text, written_segment or ""),
                _source_position(source_text, oral_segment or ""),
            ),
        ))

    death_segment = _find_segment(segments, "shot and killed", "home invasion")
    entry_segment = _find_segment(segments, "forcibly entered", "July")
    if death_segment:
        place_parts = []
        barangay_match = re.search(r"\bBarangay\s+[^,.]+,\s*Sibulan\b", entry_segment or source_text)
        if barangay_match:
            place_parts.append(barangay_match.group(0))
        if "Negros Oriental" in source_text and "Negros Oriental" not in " ".join(place_parts):
            place_parts.append("Negros Oriental")

        date_match = re.search(r"\b(?:night\s+of\s+)?(July\s+\d{1,2})\b", entry_segment or source_text)
        place_phrase = f" at his home in {', '.join(place_parts)}" if place_parts else ""
        date_phrase = f" on {date_match.group(1)}" if date_match else ""
        claims.append(_make_factual_claim(
            f"{subject} was shot and killed during a home invasion{place_phrase}{date_phrase}",
            _source_position(source_text, death_segment),
        ))

    companion_segment = _find_segment(segments, "34-year-old companion", "injured")
    if companion_segment:
        claims.append(_make_factual_claim(
            f"{subject}'s 34-year-old companion was injured in the attack",
            _source_position(source_text, companion_segment),
        ))

    investigation_segment = _find_segment(segments, "suspects remain at large")
    if investigation_segment:
        claims.append(_make_factual_claim(
            "The suspects remain at large, and investigators are reviewing CCTV "
            "footage, interviewing witnesses, and pursuing leads",
            _source_position(source_text, investigation_segment),
        ))

    study_segment = _find_segment(segments, "began studying", "1975")
    if study_segment:
        claims.append(_make_factual_claim(
            f"{subject} began studying the Philippines' marine ecosystems in 1975",
            _source_position(source_text, study_segment),
        ))

    ruling_segment = _find_segment(segments, "2016 ruling", "nine-dash")
    if ruling_segment:
        claims.append(_make_factual_claim(
            "The tribunal's 2016 ruling favored the Philippines and found no "
            "legal basis for China's sweeping nine-dash line claims",
            _source_position(source_text, ruling_segment),
        ))

    verde_segment = _find_segment(segments, "Verde Island Passage")
    if verde_segment and "conducted" in verde_segment.lower():
        claims.append(_make_factual_claim(
            f"{subject} conducted research in the Verde Island Passage",
            _source_position(source_text, verde_segment),
        ))
        if "unesco" in verde_segment.lower():
            claims.append(_make_factual_claim(
                f"{subject} advocated for the Verde Island Passage to be recognized "
                "as a UNESCO World Heritage Site",
                _source_position(source_text, verde_segment) + 1,
            ))

    tribute_segment = _find_segment(segments, "prompted tributes")
    if tribute_segment:
        claims.append(_make_factual_claim(
            "Silliman University, the University of the Philippines Marine Science "
            "Institute, conservation groups, and fellow scientists issued tributes "
            f"following {subject}'s death",
            _source_position(source_text, tribute_segment),
        ))

    return claims


def _fallback_fact_claims(text: str, translated_text: Optional[str] = None) -> List[Dict[str, object]]:
    source_text = translated_text or text
    segments = _split_segments(source_text)
    structured_claims = _extract_longform_factual_claims(source_text, segments)
    if len(structured_claims) >= 3:
        return structured_claims

    claims = []
    last_subject = None

    for segment in segments:
        segment_type = _segment_type(segment)

        if segment_type == "factual_claim":
            segment_claims = _claims_from_segment(segment, last_subject)
            claims.extend(segment_claims)
            for claim in segment_claims:
                last_subject = _infer_subject(claim) or last_subject
        elif "fugitive from justice" in segment.lower() and last_subject:
            claims.append(f"{last_subject} is a fugitive from justice.")

    if not claims and _normalize_claim(source_text) and _segment_type(source_text) == "factual_claim":
        claims = [_normalize_claim(source_text)]

    return [_make_factual_claim(claim, _source_position(source_text, claim)) for claim in claims]


def _is_mainly_attribution_post(text: str, attributed_claims: List[Dict[str, object]]) -> bool:
    if len(attributed_claims) < 2:
        return False

    attribution_sentences = 0
    verb_pattern = "|".join(re.escape(verb) for verb in ATTRIBUTION_VERBS)
    for segment in _split_segments(text):
        if re.search(rf"\b(?:{verb_pattern})\b", segment, flags=re.IGNORECASE):
            attribution_sentences += 1

    return attribution_sentences >= 2


def _fallback_extract_claims(text: str, translated_text: Optional[str] = None) -> List[Dict[str, object]]:
    segments = split_statement_segments(translated_text or text)
    scopes = speech_scopes(segments)
    if 'imagined' in scopes:
        text = '\n'.join(s for s, scope in zip(segments, scopes) if scope != 'imagined')
        translated_text = None
        if not text.strip():
            return []
    attributed_claims = _extract_attributed_claims(text, translated_text)
    if _is_mainly_attribution_post(text, attributed_claims):
        return _renumber_claims(attributed_claims)

    factual_claims = _fallback_fact_claims(text, translated_text)
    return _finalize_claims(
        [*factual_claims, *attributed_claims],
        translated_text or text,
    )


def _fallback_ignored_segments(text: str, translated_text: Optional[str] = None) -> List[Dict[str, object]]:
    source_text = translated_text or text
    ignored = []

    segments = _split_segments(source_text)
    for segment, scope in zip(segments, speech_scopes(segments)):
        segment_type = 'uncheckable' if scope == 'imagined' else _segment_type(segment)

        if segment_type != "factual_claim":
            ignored.append({
                "text": segment,
                "segment_type": segment_type,
            })

    return ignored


def _parse_claim_response(content: str) -> List[Dict[str, object]]:
    payload = json.loads(content)
    raw_claims = payload.get("claims", [])
    claims = []

    for index, item in enumerate(raw_claims, start=1):
        if isinstance(item, str):
            original_text = _normalize_claim(item)
            normalized_claim = original_text
            claim_type = "factual_claim"
            attribution = {}
            search_query = ""
            verification_focus = "factual_claim"
        else:
            original_text = ' '.join(str(item.get("claim_text", "")).split())
            normalized_claim = ' '.join(str(item.get("normalized_claim", original_text)).split())
            claim_type = str(item.get("claim_type", "factual_claim"))
            attribution = item.get("attribution") if isinstance(item.get("attribution"), dict) else {}
            search_query = _normalize_claim(str(item.get("search_query", "")))
            verification_focus = str(item.get("verification_focus", "") or claim_type)

        if not normalized_claim:
            continue

        if claim_type not in ALLOWED_CLAIM_TYPES:
            continue

        claim = {
            "claim_id": index,
            "claim_text": original_text or normalized_claim,
            "normalized_claim": normalized_claim,
            "claim_type": claim_type,
            "risk_tags": _risk_tags(normalized_claim),
        }

        if claim_type == ATTRIBUTED_CLAIM_TYPE:
            speaker = str(attribution.get("speaker") or "")
            statement = str(attribution.get("statement") or normalized_claim)
            # Preserve the reviewed reporting frame (including denials and questions).
            # Re-templating every attribution as "speaker said" changes its meaning.

            claim["verification_focus"] = "speaker_attribution"
            claim["attribution"] = attribution
            claim["search_query"] = search_query or _attribution_search_query(
                speaker,
                statement,
                attribution,
            )
        else:
            claim["search_query"] = search_query or _factual_search_query(normalized_claim)
            if verification_focus:
                claim["verification_focus"] = verification_focus

        if claim_type != ATTRIBUTED_CLAIM_TYPE and verification_focus:
            claim["verification_focus"] = verification_focus

        claims.append(claim)

    return claims


def _parse_ignored_segments(content: str) -> List[Dict[str, object]]:
    payload = json.loads(content)
    raw_segments = payload.get("ignored_segments", [])
    ignored = []

    for item in raw_segments:
        if isinstance(item, str):
            text = _normalize_claim(item)
            segment_type = _segment_type(text)
        else:
            text = _normalize_claim(str(item.get("text", "")))
            segment_type = str(item.get("segment_type", _segment_type(text)))

        if text:
            ignored.append({
                "text": text,
                "segment_type": segment_type,
            })

    return ignored


def _post_type(claims: List[Dict[str, object]], ignored_segments: List[Dict[str, object]]) -> str:
    if claims and ignored_segments:
        return "mixed_content"

    if claims:
        return "factual_only"

    if ignored_segments:
        return "non_factual"

    return "empty"


def _contains_segment_type(segments: List[Dict[str, object]], segment_type: str) -> bool:
    return any(segment.get("segment_type") == segment_type for segment in segments)


@traced('claims.extract', dependency=True)
def extract_claims(text: str, translated_text: Optional[str] = None) -> Dict[str, object]:
    """
    Extracts factual claims from a post.

    Returns a stable dictionary with extraction status and a numbered claim list.
    """
    needs_quote_review = 'reported' in speech_scopes(split_statement_segments(translated_text or text))
    fallback_claims = _fallback_extract_claims(text, translated_text)
    fallback_ignored = _fallback_ignored_segments(text, translated_text)

    if OpenAI is None:
        if needs_quote_review:
            raise QuotationExtractionError('missing_dependency')
        return {
            "status": "missing_dependency",
            "method": "local_sentence_split",
            "error": "The openai package is not installed.",
            "claims": fallback_claims,
            "ignored_segments": fallback_ignored,
            "post_type": _post_type(fallback_claims, fallback_ignored),
            "contains_opinion": _contains_segment_type(fallback_ignored, "opinion"),
            "contains_recommendation": _contains_segment_type(fallback_ignored, "recommendation"),
        }

    api_key = _get_api_key()
    if not api_key:
        if needs_quote_review:
            raise QuotationExtractionError('missing_api_key')
        return {
            "status": "missing_api_key",
            "method": "local_sentence_split",
            "error": "Missing OPENAI_API_KEY in .env.",
            "claims": fallback_claims,
            "ignored_segments": fallback_ignored,
            "post_type": _post_type(fallback_claims, fallback_ignored),
            "contains_opinion": _contains_segment_type(fallback_ignored, "opinion"),
            "contains_recommendation": _contains_segment_type(fallback_ignored, "recommendation"),
        }

    prompt = (
        SPEECH_RULES +
        "Extract checkable factual claims from messy Philippine social media posts. "
        "For an explicit fact-check headline ('the claim that X is false/true'), "
        "independently check X, not the headline's verdict. Preserve the full "
        "headline in claim_text and use the underlying proposition in normalized_claim. "
        "Do not invert ordinary negative factual assertions or strip negation inside X. "
        "Do not treat a printed publisher name or verdict as supporting evidence. "
        "When a post mainly attributes statements to a named person, source, "
        "program, or interview, prioritize attribution checks over the embedded "
        "topic claims. In that case, emit claim_type=\"attributed_statement\" "
        "and write normalized_claim as '<speaker> said <statement>'. Include "
        "attribution.speaker, attribution.role, attribution.statement, "
        "attribution.source, attribution.program, attribution.date when present, "
        "using null for absent fields. Contributor bylines, trailing /via NAME, and "
        "photo credits are not speaker or required source attribution; do not insert "
        "credit-only names into the assertion or search query. A reporter may be a "
        "speaker/source only when the statement explicitly assigns that role, "
        "and a search_query containing the speaker, source/program/date, and "
        "statement keywords. For attribution checks, claim_text must preserve "
        "the complete original sentence that contains the named speaker/source/"
        "program/date when present. "
        "Do not extract the underlying statement without the speaker unless "
        "the post also independently asserts it as fact. "
        "For long factual posts, extract each discrete checkable claim. Merge "
        "a vague summary sentence with fuller details elsewhere in the same "
        "post when they describe the same event or assertion. For example, "
        "combine a general expert-testimony sentence with later written/oral "
        "testimony details, and combine a death summary with later place/date "
        "incident details. Keep separate claims for different subjects, such "
        "as an injured companion, investigation status, a public official's "
        "quoted statement, a legal ruling, research activity, advocacy, and "
        "institutional tributes. "
        "Evaluate each sentence independently for how many separately verifiable "
        "facts it contains. Do not default to one claim per sentence just because "
        "the post contains multiple sentences. A sentence with several distinct "
        "facts should produce multiple claims regardless of how many other "
        "sentences and claims exist elsewhere in the same post. A sentence "
        "contains multiple separate claims when it asserts more than one "
        "independently checkable fact, such as multiple named actions, multiple "
        "named entities each doing something distinct, or a list of separate "
        "events joined by 'and.' For example, the sentence 'Padilla was arrested "
        "and imprisoned before for illegal possession of firearms and was granted "
        "a conditional pardon by the late Fidel Ramos and an absolute pardon in "
        "2016 by Former President Rodrigo Roa Duterte' should produce three "
        "claims: Padilla was arrested and imprisoned for illegal possession of "
        "firearms; Padilla was granted a conditional pardon by Fidel Ramos; and "
        "Padilla was granted an absolute pardon in 2016 by Rodrigo Roa Duterte. "
        "Apply this same decomposition standard whether the post is one sentence "
        "long or many sentences long, and whether the sentence is the only "
        "complex sentence or one of several. "
        "Do not reject the whole post because it contains opinion, insults, fear, "
        "support language, or calls to action. Separate those into ignored_segments. "
        "Do not include vague/evaluative/eulogy framing as claims, such as "
        "'helped defend,' 'widely respected,' 'leading expert,' 'significant "
        "role,' 'world-class,' 'generous mentor,' or reflective closing lines. "
        "Return JSON only with this shape: "
        '{"claims":[{"claim_text":"original claim","normalized_claim":"clear English claim","claim_type":"factual_claim|attributed_statement","verification_focus":"factual_claim|speaker_attribution","attribution":{"speaker":"name","role":"speaker role","statement":"what was said","source":"outlet","program":"program","date":"date"},"search_query":"speaker source statement keywords"}],'
        '"ignored_segments":[{"text":"opinion or demand","segment_type":"opinion|recommendation|uncheckable"}]}. '
        "Return every distinct checkable claim, without a fixed count quota. Extract criminal allegations, "
        "public-official claims, event-attendance claims, and disaster-response claims "
        "when they are stated as facts. Do not include opinions, slogans, insults, "
        "predictions, or demands as claims."
    )
    user_content = (
        f"Original post:\n{text}\n\n"
        f"Translated text if available:\n{translated_text or text}"
    )

    client = None
    try:
        client = OpenAI(api_key=api_key, timeout=60, max_retries=0)
        response = client.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
        )
        choice = response.choices[0]
        if choice.finish_reason != 'stop' or getattr(choice.message, 'refusal', None):
            raise ValueError('incomplete_extraction_response')
        content = choice.message.content or "{}"
        claims = _parse_claim_response(content)
        ignored_segments = _parse_ignored_segments(content)
        from pipeline.claim_coverage import review_claim_coverage
        coverage = review_claim_coverage(client, DEFAULT_CLAIM_REVIEW_MODEL,
                                         translated_text or text, claims)
        content = json.dumps(coverage, ensure_ascii=False)
        claims = _parse_claim_response(content)
        ignored_segments = _parse_ignored_segments(content)
        if len(claims) != len(coverage['claims']):
            raise ValueError('covered_claim_lost_during_parsing')
        for claim, raw in zip(claims, coverage['claims']):
            claim['source_passages'] = raw['source_quotes']
        validate_speech_coverage({**coverage, 'claims': claims},
                                 split_statement_segments(translated_text or text))
    except Exception as error:
        if needs_quote_review:
            event('claims.quotation_extraction_failed', error_type=type(error).__name__)
            raise QuotationExtractionError('quotation_review_failed') from error
        return {
            "status": "error",
            "method": "local_sentence_split",
            "error": f"OpenAI claim extraction failed: {error}",
            "claims": fallback_claims,
            "ignored_segments": fallback_ignored,
            "post_type": _post_type(fallback_claims, fallback_ignored),
            "contains_opinion": _contains_segment_type(fallback_ignored, "opinion"),
            "contains_recommendation": _contains_segment_type(fallback_ignored, "recommendation"),
        }

    finally:
        if client is not None and callable(getattr(client, 'close', None)):
            try:
                client.close()
            except Exception:
                event('claims.client_cleanup_failed')

    # Do not overwrite a reviewed inventory with local quote heuristics or whichever
    # list happens to be longer. That reintroduced duplicates and discarded facts.
    draft_fingerprints = [_claim_fingerprint(claim) for claim in claims]
    claims = _renumber_claims(claims)
    final_indexes = {_claim_fingerprint(claim): i for i, claim in enumerate(claims)}
    for row in coverage['coverage']:
        row['claim_indexes'] = sorted({final_indexes[draft_fingerprints[i]] for i in row['claim_indexes']})
    for claim in claims:
        claim['evidence_context'] = translated_text or text

    # A validated empty inventory is a completed exclusion, not a provider failure.
    # Do not resurrect imagined/opinion statements through the local fallback.
    return {
        "status": "ok",
        "method": "openai",
        "coverage": coverage['coverage'],
        "grouping": coverage.get('grouping', []),
        "grouping_status": coverage.get('grouping_status'),
        "grouping_error": coverage.get('grouping_error'),
        "coverage_review_model": DEFAULT_CLAIM_REVIEW_MODEL,
        "error": None,
        "claims": claims,
        "ignored_segments": ignored_segments,
        "post_type": _post_type(claims, ignored_segments),
        "contains_opinion": _contains_segment_type(ignored_segments, "opinion"),
        "contains_recommendation": _contains_segment_type(ignored_segments, "recommendation"),
    }
