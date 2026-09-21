"""
Content Profiler for IRIS.

The profiler decides what parts of a post are eligible for fact-checking before
the search and verdict pipeline runs. It does not decide whether a claim is
true. It only labels content type, ambiguity, and routing.
"""

from __future__ import annotations

from iris_trace.core import traced, event
from pipeline.translator import sanitize_translation
from pipeline.text_boundaries import has_reported_quote, is_attribution_tail, quote_spans, split_statement_segments
from pipeline.quotation_context import SPEECH_RULES, speech_scopes

import json
import math
import os
import re
from typing import Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment setup
    def load_dotenv():
        return False


load_dotenv()

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SEGMENT_LABELS = [
    "factual_claim",
    "opinion",
    "forecast_or_projection_detected",
    "quote",
    "satire_or_humor",
    "call_to_action",
    "contextual_background",
    "unclear",
]

POST_TYPES = {
    "fact_only",
    "opinion_only",
    "mixed_content",
    "satirical_or_comedic",
    "quote_context",
    "unclear",
}

VERIFY_ROUTES = {
    "proceed_to_verification",
    "verify_factual_claims_only",
    "proceed_with_caution",
}

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
    "this is clearly",
    "reminds us",
]

OPINION_WORDS = [
    "masama",
    "mabuti",
    "maganda",
    "pangit",
    "delikado",
    "useless",
    "desperate",
    "best",
    "worst",
    "better",
    "evil",
    "fake news",
    "widely respected",
    "leading expert",
    "leading experts",
    "world-class",
    "generous mentor",
]

GENERIC_COMPARATIVES = {"best", "better", "worst"}

REPORTED_SPEECH = re.compile(
    r"\b(?:opens? up|opened up|shared|shares|said|says|told|tells|revealed|reveals|recalled|"
    r"recalls|admitted|admits|explained|explains|talked about|talks about|spoke about|"
    r"speaks about|described|describes|according to)\b")

CALL_TO_ACTION_MARKERS = [
    "should",
    "must",
    "dapat",
    "kailangan",
    "please share",
    "share this",
    "vote",
    "iboto",
    "panawagan",
    "revoke",
    "confiscate",
    "disarm",
    "ban",
    "boycott",
    "support",
]

FACTUAL_MARKERS = [
    "according to",
    "reported",
    "announced",
    "confirmed",
    "released",
    "issued",
    "filed",
    "approved",
    "signed",
    "recorded",
    "stated",
    "said",
    "asked",
    "answered",
    "replied",
    "furthered",
    "cited",
    "found",
    "arrested",
    "visited",
    "occurred",
    "died",
    "killed",
    "shot",
    "injured",
    "entered",
    "forcibly entered",
    "remain at large",
    "reviewing",
    "interviewing",
    "pursuing leads",
    "condemned",
    "vowed",
    "began",
    "studying",
    "submitted",
    "delivered",
    "testimony",
    "evidence",
    "ruling",
    "favored",
    "rejected",
    "no legal basis",
    "conducted",
    "research",
    "recognized",
    "tributes",
    "prompted tributes",
    "audit observation memorandum",
    "confidential funds",
    "confidential agents",
    "joint circular",
    "classified",
    "evaluation",
    "terrorism threats",
    "security threats",
    "launched",
    "declared",
    "ayon",
    "ayon kay",
    "sinabi",
    "iniulat",
    "inulat",
    "nag-ulat",
    "nag-anunsyo",
    "inanunsyo",
    "naglabas",
    "inilabas",
    "inaprubahan",
    "pinirmahan",
]

ENTITY_MARKERS = [
    "department of health",
    "doh",
    "department of education",
    "deped",
    "department of justice",
    "doj",
    "dilg",
    "pnp",
    "police",
    "tribunal",
    "university",
    "unesco",
    "silliman university",
    "university of the philippines",
    "marine science institute",
    "comelec",
    "senate",
    "house of representatives",
    "congress",
    "malacanang",
    "philippine statistics authority",
    "psa",
    "pagasa",
    "philippine coast guard",
    "pcg",
    "armed forces of the philippines",
    "afp",
    "president",
    "vice president",
    "senator",
    "senator-judge",
    "auditor",
    "state auditor",
    "witness",
    "bangsamoro autonomous region",
    "barmm",
    "new people's army",
    "npa",
    "mayor",
    "governor",
]

FORECAST_MARKERS = [
    "forecast",
    "forecasted",
    "projection",
    "projected",
    "expected",
    "expects",
    "likely",
    "could",
    "will",
    "soon",
    "posibleng",
    "maaaring",
    "inaasahan",
    "tatama",
    "babagsak",
]

FUTURE_TIME_MARKERS = [
    "tomorrow",
    "next week",
    "next month",
    "next year",
    "by 20",
    "in 20",
    "sa susunod na linggo",
    "sa susunod na buwan",
    "sa susunod na taon",
]

FORECAST_DOMAIN_MARKERS = [
    "weather",
    "rainfall",
    "bagyo",
    "typhoon",
    "storm",
    "economy",
    "inflation",
    "market",
    "stock",
    "public health",
    "covid",
    "dengue",
    "cases",
    "surge",
    "military",
    "security risk",
]

QUOTE_MARKERS = [
    "said",
    "stated",
    "according to",
    "quote",
    "quoted",
    "interview",
    "statement",
    "remarks",
    "sinabi",
    "ayon kay",
    "pahayag",
    "panayam",
]

SATIRE_MARKERS = [
    "satire",
    "satirical",
    "parody",
    "meme",
    "joke",
    "punchline",
    "haha",
    "lol",
    "charot",
    "eme",
    "as if",
    "comedian",
    "nakakatawa",
]

VAGUE_MARKERS = [
    "someone said",
    "they said",
    "people say",
    "may nagsabi",
    "sabi nila",
    "kumakalat",
    "viral daw",
    "allegedly",
    "daw",
    "raw",
]

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on local environment setup
    OpenAI = None


def _get_api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _clean_segment(text: str) -> str:
    text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", text)
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
        segment = _clean_segment(part)
        if segment:
            segments.extend(
                split_segment
                for split_segment in _split_leading_headline_question(segment)
                if split_segment
            )

    return segments


def _align_translated_segments(text: str, translated_text: Optional[str]) -> List[Optional[str]]:
    source_segments = _split_segments(text)

    if not translated_text or translated_text == text:
        return [None for _ in source_segments]

    translated_segments = _split_segments(translated_text)
    if len(translated_segments) != len(source_segments):
        return [None for _ in source_segments]

    return translated_segments


def _has_term(normalized_text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized_text))


def _matched_terms(normalized_text: str, terms: List[str]) -> List[str]:
    return [term for term in terms if _has_term(normalized_text, term)]


def _has_number(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:[,.]\d+)*(?:%| percent| porsyento)?\b", text))


def _has_named_person_or_place(text: str) -> bool:
    return bool(re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b", text))


def _clamp_score(score: float) -> float:
    return round(max(0.05, min(0.95, score)), 2)


def _opinion_words(segment: str, normalized: str) -> List[str]:
    """
    Opinion words that are the post's own judgement, not part of what someone is reported saying.

    "Atasha Muhlach opens up about the best advice she received" reports what she said; the
    superlative is hers, not the post's. A generic comparative in a sentence that attributes
    speech to a named person no longer marks it as opinion, which had set aside every sentence of
    that post but its hashtags (diagnosed 22 September). Opinion phrases and every other opinion
    word still count, and so does a comparative with nobody named.
    """
    words = _matched_terms(normalized, OPINION_WORDS)
    if (words and set(words) <= GENERIC_COMPARATIVES and _has_named_person_or_place(segment)
            and REPORTED_SPEECH.search(normalized)):
        return []
    return words


def _base_scores(segment: str) -> Tuple[Dict[str, float], Dict[str, List[str]]]:
    normalized = _normalize(segment)
    word_count = len(segment.split())
    matches = {
        "factual": _matched_terms(normalized, FACTUAL_MARKERS),
        "entities": _matched_terms(normalized, ENTITY_MARKERS),
        "opinion_phrases": _matched_terms(normalized, OPINION_PHRASES),
        "opinion_words": _opinion_words(segment, normalized),
        "call_to_action": _matched_terms(normalized, CALL_TO_ACTION_MARKERS),
        "forecast": _matched_terms(normalized, FORECAST_MARKERS),
        "future_time": _matched_terms(normalized, FUTURE_TIME_MARKERS),
        "forecast_domain": _matched_terms(normalized, FORECAST_DOMAIN_MARKERS),
        "quote": _matched_terms(normalized, QUOTE_MARKERS),
        "satire": _matched_terms(normalized, SATIRE_MARKERS),
        "vague": _matched_terms(normalized, VAGUE_MARKERS),
    }

    scores = {label: 0.05 for label in SEGMENT_LABELS}

    factual_score = 0.10
    factual_score += min(0.50, 0.22 * len(matches["factual"]))
    factual_score += min(0.30, 0.12 * len(matches["entities"]))
    if matches["factual"] and matches["entities"]:
        factual_score += 0.18
    if _has_number(segment):
        factual_score += 0.22
    if _has_named_person_or_place(segment):
        factual_score += 0.10
    if word_count >= 5 and re.search(r"\b(?:is|are|was|were|has|have|had)\b", normalized):
        factual_score += 0.10
    scores["factual_claim"] = factual_score

    opinion_score = 0.05
    opinion_score += min(0.55, 0.45 * len(matches["opinion_phrases"]))
    opinion_score += min(0.45, 0.12 * len(matches["opinion_words"]))
    if matches["opinion_words"]:
        opinion_score += 0.30
    if "!" in segment and matches["opinion_words"]:
        opinion_score += 0.08
    scores["opinion"] = opinion_score

    call_score = 0.05 + min(0.75, 0.30 * len(matches["call_to_action"]))
    scores["call_to_action"] = call_score

    forecast_score = 0.05
    if matches["forecast"]:
        forecast_score += 0.32
    if matches["future_time"]:
        forecast_score += 0.24
    if matches["forecast_domain"]:
        forecast_score += 0.16
    if ("will" in matches["forecast"] or "could" in matches["forecast"]) and matches["future_time"]:
        forecast_score += 0.12
    scores["forecast_or_projection_detected"] = forecast_score

    quote_score = 0.05
    if quote_spans(segment):
        quote_score += 0.28
    quote_score += min(0.55, 0.20 * len(matches["quote"]))
    if _has_reported_quote(segment):
        quote_score = max(quote_score, 0.53)
    scores["quote"] = quote_score

    satire_score = 0.05 + min(0.80, 0.35 * len(matches["satire"]))
    if re.search(r"\b[A-Z]{4,}\b", segment) and matches["satire"]:
        satire_score += 0.10
    scores["satire_or_humor"] = satire_score

    unclear_score = 0.05
    if word_count < 3:
        unclear_score += 0.45
    if matches["vague"]:
        unclear_score += 0.35
    if factual_score < 0.45 and opinion_score < 0.45 and forecast_score < 0.45:
        unclear_score += 0.25
    scores["unclear"] = unclear_score

    if normalized.startswith(("background:", "context:", "for context")):
        scores["contextual_background"] = 0.55

    return ({label: _clamp_score(score) for label, score in scores.items()}, matches)


def _ordered_labels(scores: Dict[str, float]) -> List[Tuple[str, float]]:
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def _segment_notification(route: str) -> Optional[str]:
    messages = {
        "stop_opinion_detected": (
            "IRIS did not verify this segment because it appears to be opinion "
            "or value judgment rather than a checkable factual claim."
        ),
        "stop_forecast_projection": (
            "IRIS skipped this segment because it appears to be a forecast or "
            "projection. IRIS can check whether a forecast was reported, but "
            "does not verify forecast accuracy."
        ),
        "quote_context_review": (
            "IRIS found quote-context signals. A full quote check needs enough "
            "context to identify the speaker, statement, and source."
        ),
        "stop_no_checkable_claims": (
            "IRIS could not identify a specific checkable factual claim in this "
            "segment."
        ),
        "proceed_with_caution": (
            "IRIS found a possible factual claim, but the content has mixed or "
            "low-confidence signals."
        ),
    }
    return messages.get(route)


def _reason_codes(scores: Dict[str, float], matches: Dict[str, List[str]], score_gap: float) -> List[str]:
    reasons = []

    if scores["opinion"] >= 0.45:
        reasons.append("emotional_or_persuasive_language")
    if scores["call_to_action"] >= 0.45:
        reasons.append("call_to_action")
    if scores["forecast_or_projection_detected"] >= 0.65:
        reasons.append("forecast_or_projection_detected")
    if scores["quote"] >= 0.45:
        reasons.append("quote_context_needed")
    if scores["satire_or_humor"] >= 0.70:
        reasons.append("satire_or_humor")
    if scores["unclear"] >= 0.55 or matches["vague"]:
        reasons.append("vague_claim")
    if score_gap < 0.10:
        reasons.append("low_classifier_confidence")
    if scores["factual_claim"] >= 0.55 and scores["opinion"] >= 0.45:
        reasons.append("mixed_fact_opinion")

    return sorted(set(reasons))


def _has_reported_quote(segment: str) -> bool:
    return has_reported_quote(segment)


def _is_headline_question(segment: str) -> bool:
    stripped = segment.strip(" \"'`“”‘’")
    if not stripped.endswith("?") or len(stripped.split()) > 8:
        return False

    letters = re.findall(r"[A-Za-z]", stripped)
    uppercase = re.findall(r"[A-Z]", stripped)
    return bool(letters) and len(uppercase) / len(letters) >= 0.70


def _is_reported_or_scheduled_event(segment: str) -> bool:
    return bool(re.search(
        r"\b(?:announced|scheduled|proclaimed|announces|reported|sinabi|iniulat|"
        r"inanunsyo|nakatakda)\b|\bwill\s+be\s+(?:proclaimed|awarded|held|opened)\b",
        segment, re.I,
    ))


def _route_segment(segment: str, segment_id: str, translated_segment: Optional[str]) -> Dict[str, object]:
    scores, matches = _base_scores(segment)
    ordered = _ordered_labels(scores)
    top_label, top_score = ordered[0]
    second_label, second_score = ordered[1]
    score_gap = round(top_score - second_score, 2)
    factual_score = scores["factual_claim"]

    eligible = False
    route = "stop_no_checkable_claims"

    if _is_headline_question(segment):
        top_label = "unclear"
        top_score = max(scores["unclear"], top_score)
        eligible = False
        route = "stop_no_checkable_claims"
    elif _has_reported_quote(segment):
        top_label = "factual_claim"
        top_score = factual_score
        eligible = True
        route = "proceed_with_caution"
    elif (scores["forecast_or_projection_detected"] >= 0.65
          and _is_reported_or_scheduled_event(segment)):
        top_label = "factual_claim"
        top_score = factual_score
        eligible = True
        route = "proceed_with_caution"
    elif scores["forecast_or_projection_detected"] >= 0.65:
        top_label = "forecast_or_projection_detected"
        top_score = scores[top_label]
        eligible = False
        route = "stop_forecast_projection"
    elif factual_score >= 0.75:
        top_label = "factual_claim"
        top_score = factual_score
        eligible = True
        route = "proceed_to_verification"
    elif factual_score >= 0.55 and (
        scores["opinion"] >= 0.45 or scores["quote"] >= 0.45 or score_gap < 0.10
    ):
        top_label = "factual_claim"
        top_score = factual_score
        eligible = True
        route = "proceed_with_caution"
    elif factual_score >= 0.55:
        top_label = "factual_claim"
        top_score = factual_score
        eligible = True
        route = "proceed_with_caution"
    elif scores["opinion"] >= 0.45 and factual_score < 0.50:
        top_label = "opinion"
        top_score = scores[top_label]
        eligible = False
        route = "stop_opinion_detected"
    elif scores["call_to_action"] >= 0.65 and factual_score < 0.50:
        top_label = "call_to_action"
        top_score = scores[top_label]
        eligible = False
        route = "stop_opinion_detected"
    elif scores["satire_or_humor"] >= 0.70 and factual_score < 0.75:
        top_label = "satire_or_humor"
        top_score = scores[top_label]
        eligible = False
        route = "stop_no_checkable_claims"
    elif scores["quote"] >= 0.70 and factual_score < 0.50:
        top_label = "quote"
        top_score = scores[top_label]
        eligible = False
        route = "quote_context_review"
    elif top_score < 0.55 or score_gap < 0.10 or scores["unclear"] >= 0.55:
        top_label = "unclear"
        top_score = max(scores["unclear"], top_score)
        eligible = False
        route = "stop_no_checkable_claims"

    reasons = _reason_codes(scores, matches, score_gap)
    if _has_reported_quote(segment):
        reasons = sorted(set(reasons + ["reported_attribution_needs_verification"]))

    # A weak keyword score is not evidence that a statement is uncheckable.
    # Keep plausible statements for the actual claim extractor to assess.
    if (not eligible and top_label == "unclear" and len(segment.split()) >= 5
            and not segment.rstrip(" \"'\u201c\u201d\u2018\u2019").endswith("?")):
        eligible = True
        route = "proceed_with_caution"
        reasons = sorted(set(reasons + ["needs_claim_extraction_review"]))
    if _has_term(_normalize(segment), "imaginary"):
        reasons = sorted(set(reasons + ["imaginary_qualifier_needs_context"]))
        if eligible:
            route = "proceed_with_caution"

    return {
        "segment_id": segment_id,
        "text": segment,
        "translated_text": translated_segment,
        "scores": scores,
        "top_label": top_label,
        "top_label_score": _clamp_score(top_score),
        "second_label": second_label,
        "second_label_score": second_score,
        "score_gap": score_gap,
        "eligible_for_verification": eligible,
        "recommended_route": route,
        "reason_codes": reasons,
        "user_notification": _segment_notification(route) if route == "proceed_with_caution"
        else (None if eligible else _segment_notification(route)),
    }


def _legacy_segment_type(segment: Dict[str, object]) -> str:
    label = str(segment["top_label"])

    if label == "call_to_action":
        return "recommendation"
    if label == "forecast_or_projection_detected":
        return "forecast_or_projection"
    if label == "satire_or_humor":
        return "satire_or_humor"

    return label


def _ignored_segments(segments: List[Dict[str, object]]) -> List[Dict[str, object]]:
    ignored = []

    for segment in segments:
        if segment["eligible_for_verification"]:
            continue

        ignored.append({
            "segment_id": segment["segment_id"],
            "text": segment["text"],
            "segment_type": _legacy_segment_type(segment),
            "reason_codes": segment["reason_codes"],
            "recommended_route": segment["recommended_route"],
            "user_notification": segment["user_notification"],
        })

    return ignored


def _post_type(segments: List[Dict[str, object]]) -> str:
    if not segments:
        return "unclear"

    eligible = [segment for segment in segments if segment["eligible_for_verification"]]
    ignored = [segment for segment in segments if not segment["eligible_for_verification"]]
    labels = {str(segment["top_label"]) for segment in segments}

    if eligible and ignored:
        return "mixed_content"
    if eligible:
        return "unclear" if "unclear" in labels else "fact_only"
    if "opinion" in labels or "call_to_action" in labels:
        return "opinion_only"
    if "satire_or_humor" in labels:
        return "satirical_or_comedic"
    if "quote" in labels:
        return "quote_context"

    return "unclear"


def _recommended_route(segments: List[Dict[str, object]], post_type: str) -> str:
    eligible = [segment for segment in segments if segment["eligible_for_verification"]]

    if eligible:
        if len(eligible) == len(segments):
            if any(segment["recommended_route"] == "proceed_with_caution" for segment in eligible):
                return "proceed_with_caution"
            return "proceed_to_verification"
        return "verify_factual_claims_only"

    routes = {str(segment["recommended_route"]) for segment in segments}

    if "stop_forecast_projection" in routes:
        return "stop_forecast_projection"
    if post_type == "opinion_only":
        return "stop_opinion_detected"
    if post_type == "quote_context":
        return "quote_context_review"

    return "stop_no_checkable_claims"


def _post_notification(route: str, ignored: List[Dict[str, object]]) -> Optional[str]:
    if route in VERIFY_ROUTES:
        if ignored:
            return "IRIS will verify only the factual segments and skip non-checkable parts."
        return None

    messages = {
        "stop_opinion_detected": (
            "This appears to be opinion or commentary, so IRIS did not perform "
            "fact-checking."
        ),
        "stop_forecast_projection": (
            "IRIS does not verify forecast or projection accuracy. It can only "
            "check whether such forecasts were reported by credible or official "
            "sources."
        ),
        "quote_context_review": (
            "IRIS needs clearer quote context before it can verify the quoted "
            "statement."
        ),
        "stop_no_checkable_claims": (
            "IRIS did not find factual claims that can be checked against "
            "approved sources."
        ),
    }
    return messages.get(route)


def _confidence(segments: List[Dict[str, object]]) -> float:
    if not segments:
        return 0.0

    scores = [float(segment["top_label_score"]) for segment in segments]
    return round(sum(scores) / len(scores), 2)


def _ambiguity_score(segments: List[Dict[str, object]], post_type: str) -> float:
    if not segments:
        return 0.90

    low_gap_scores = [
        max(0.0, 0.20 - float(segment["score_gap"])) / 0.20
        for segment in segments
    ]
    base = sum(low_gap_scores) / len(low_gap_scores)

    if post_type == "mixed_content":
        base = max(base, 0.60)
    if any("vague_claim" in segment["reason_codes"] for segment in segments):
        base = max(base, 0.65)

    return round(min(0.95, base), 2)


def _contains_label(segments: List[Dict[str, object]], label: str, minimum: float = 0.45) -> bool:
    return any(float(segment["scores"].get(label, 0.0)) >= minimum for segment in segments)


def _build_profile(
    text: str,
    translated_text: Optional[str],
    segments: List[Dict[str, object]],
    method: str,
    status: str,
    error: Optional[str],
    openai_profile: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    # Reapply source-grounded framing after AI advice as well as local routing.
    scopes = speech_scopes([str(s['text']) for s in segments])
    for segment, scope in zip(segments, scopes):
        segment['speech_scope'] = scope
        if scope == 'imagined':
            segment.update(eligible_for_verification=False, top_label='satire_or_humor',
                           recommended_route='stop_no_checkable_claims',
                           user_notification='This describes imagined or anticipated speech, not a reported statement.')
            segment['reason_codes'] = sorted(set(segment['reason_codes'] + ['imagined_speech_not_reported']))
        elif scope in {'reported', 'reported_indirect'}:
            segment.update(eligible_for_verification=True, top_label='factual_claim',
                           recommended_route='proceed_with_caution')
            segment['reason_codes'] = sorted(set(segment['reason_codes'] + ['reported_attribution_needs_verification']))
    ignored = _ignored_segments(segments)
    post_type = _post_type(segments)
    route = _recommended_route(segments, post_type)
    eligible_segments = [
        segment for segment in segments if segment["eligible_for_verification"]
    ]
    verification_text = "\n".join(str(segment["text"]) for segment in eligible_segments).strip()
    normalized_verification_text = "\n".join(
        str(segment.get("translated_text") or segment["text"])
        for segment in eligible_segments
    ).strip()
    ambiguity_reasons = sorted({
        reason
        for segment in segments
        for reason in segment["reason_codes"]
    })

    return {
        "status": status,
        "method": method,
        "error": error,
        "post_type": post_type,
        "confidence": _confidence(segments),
        "ambiguity_score": _ambiguity_score(segments, post_type),
        "ambiguity_reasons": ambiguity_reasons,
        "contains_factual_claims": bool(eligible_segments),
        "contains_opinion": _contains_label(segments, "opinion"),
        "contains_recommendation": _contains_label(segments, "call_to_action"),
        "contains_forecast_or_projection": _contains_label(
            segments,
            "forecast_or_projection_detected",
            0.65,
        ),
        "contains_satire_or_humor": _contains_label(segments, "satire_or_humor", 0.70),
        "contains_quote": _contains_label(segments, "quote"),
        "eligible_for_verification": bool(eligible_segments),
        "recommended_route": route,
        "verification_text": verification_text or text,
        "normalized_verification_text": normalized_verification_text or translated_text or text,
        "segments": segments,
        "ignored_segments": ignored,
        "user_notification": _post_notification(route, ignored),
        "openai_profile": openai_profile or {
            "used": False,
            "status": "not_run",
            "error": None,
            "result": None,
        },
    }


@traced('text.profile_local', dependency=False)
def _local_profile(text: str, translated_text: Optional[str]) -> Dict[str, object]:
    source_segments = _split_segments(text)
    translated_segments = _align_translated_segments(text, translated_text)
    segments = [
        _route_segment(segment, f"s{index}", translated_segments[index - 1])
        for index, segment in enumerate(source_segments, start=1)
    ]

    return _build_profile(
        text=text,
        translated_text=translated_text,
        segments=segments,
        method="local_rules",
        status="ok",
        error=None,
    )


def _needs_openai_profile(profile: Dict[str, object]) -> bool:
    if any("needs_claim_extraction_review" in segment["reason_codes"]
           for segment in profile["segments"]):
        return True
    if profile["post_type"] in {"mixed_content", "satirical_or_comedic", "quote_context", "unclear"}:
        return True

    return bool(profile["ambiguity_reasons"]) and float(profile["ambiguity_score"]) >= 0.60


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


@traced('text.profile_ai', dependency=True)
def _request_openai_profile(
    text: str,
    translated_text: Optional[str],
    local_profile: Dict[str, object],
) -> Dict[str, object]:
    if OpenAI is None:
        return {
            "used": False,
            "status": "missing_dependency",
            "error": "The openai package is not installed.",
            "result": None,
        }

    api_key = _get_api_key()
    if not api_key:
        return {
            "used": False,
            "status": "missing_api_key",
            "error": "Missing OPENAI_API_KEY in .env.",
            "result": None,
        }

    system_prompt = (
        SPEECH_RULES +
        "You are the IRIS Content Profiler. Classify the content type of a "
        "Philippines-related online post before fact-checking. Do not decide "
        "truth or falsity. Return JSON only. Use fixed segment labels: "
        "A fact-check headline saying a concrete claim 'is false' or 'is true' "
        "is checkable, not opinion merely because it contains a verdict. "
        "Preserve the assertion and route it for independent verification; "
        "a screenshot's publisher and printed verdict are not evidence. "
        "Treat local labels as weak hints, not answers to copy. Classify every "
        "provided segment ID. Low confidence alone is not a reason to discard "
        "a possible factual statement. Reunion reports, attributed denials, "
        "dated numerical observations, and announcements of scheduled honors "
        "are checkable. Distinguish a reported announcement or forecast from "
        "a prediction of what will actually happen. Preserve named subjects, "
        "Keep a complete attributed quotation together, including questions, "
        "recommendations and hypothetical comparisons: the checkable assertion "
        "is that the speaker said it, not that the quoted scenario happened. "
        "negation, dates, amounts, and imaginary/satirical qualifiers. Do not "
        "invent context, rewrite the source text, or determine a verdict. "
        "factual_claim, opinion, forecast_or_projection_detected, quote, "
        "satire_or_humor, call_to_action, contextual_background, unclear. Use "
        "fixed routes: proceed_to_verification, verify_factual_claims_only, "
        "proceed_with_caution, stop_opinion_detected, stop_no_checkable_claims, "
        "stop_forecast_projection, quote_context_review."
    )
    user_prompt = json.dumps({
        "original_text": text,
        "translated_text": translated_text or text,
        "local_segments": [
            {
                "segment_id": segment["segment_id"],
                "text": segment["text"],
                "translated_text": segment.get("translated_text"),
                "local_top_label": segment["top_label"],
                "local_reason_codes": segment["reason_codes"],
            }
            for segment in local_profile["segments"]
        ],
        "output_requirements": {
            "segments": "An array with one object for EVERY supplied segment ID, in source order.",
            "segment_id": "The exact supplied ID, not a new ID.",
            "top_label": SEGMENT_LABELS,
            "top_label_score": "A number from 0 to 1 reflecting your actual uncertainty; advisory only.",
            "eligible_for_verification": "JSON boolean: true for a checkable factual assertion or reported attribution.",
            "reason_codes": "An array of brief classification reasons, not verdicts.",
        },
    })

    try:
        client = OpenAI(api_key=api_key, timeout=30, max_retries=1)
        response = client.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        if not isinstance(result, dict) or not isinstance(result.get("segments"), list):
            raise ValueError("Invalid profiler response shape")
        known_ids = {segment["segment_id"] for segment in local_profile["segments"]}
        seen = set()
        for segment in result["segments"]:
            if not isinstance(segment, dict):
                raise ValueError("Invalid profiler segment")
            segment_id = segment.get("segment_id")
            if (not isinstance(segment_id, str) or segment_id not in known_ids or segment_id in seen
                    or segment.get("top_label") not in SEGMENT_LABELS
                    or type(segment.get("eligible_for_verification")) is not bool):
                raise ValueError("Invalid profiler segment fields")
            seen.add(segment_id)
        if seen != known_ids:
            event("text.profile_advice_incomplete", missing_segment_ids=sorted(known_ids - seen))
    except Exception as error:
        return {
            "used": False,
            "status": "error",
            "error": f"OpenAI content profiling failed: {error}",
            "result": None,
        }

    return {
        "used": True,
        "status": "ok",
        "error": None,
        "result": result,
    }


@traced('text.profile_merge', dependency=False)
def _merge_openai_segment_advice(
    local_profile: Dict[str, object],
    openai_profile: Dict[str, object],
) -> Dict[str, object]:
    ai_result = openai_profile.get("result")
    if not isinstance(ai_result, dict) or not isinstance(ai_result.get("segments"), list):
        return local_profile
    ai_segments = {
        str(segment.get("segment_id")): segment
        for segment in ai_result.get("segments", [])
        if isinstance(segment, dict)
    }

    if not ai_segments:
        return local_profile

    updated_segments = []
    for segment in local_profile["segments"]:
        updated = dict(segment)
        ai_segment = ai_segments.get(str(segment["segment_id"]))

        if ai_segment:
            ai_label = str(ai_segment.get("top_label", ""))
            ai_score = _safe_float(ai_segment.get("top_label_score"))
            ai_eligible = ai_segment.get("eligible_for_verification") is True

            # A quotation the model finds checkable is checkable: what IRIS checks is that the
            # speaker said it. Advice labelled "quote" used to be dropped, which set aside the
            # quotation of the Atasha Muhlach post (22 September). Imagined or anticipated speech
            # is still stopped by the speech rules applied when the profile is rebuilt below.
            if (
                ai_eligible
                and ai_label in {"factual_claim", "quote"}
            ):
                # Routing is not a verdict. An uncalibrated generated number
                # must not veto an explicit finding of checkable content.
                updated["top_label"] = "factual_claim"
                updated["top_label_score"] = _clamp_score(max(float(updated["top_label_score"]), ai_score))
                updated["eligible_for_verification"] = True
                updated["recommended_route"] = "proceed_with_caution"
                updated["reason_codes"] = sorted(set(
                    list(updated["reason_codes"]) + ["openai_factual_claim_advice"]
                ))
                updated["user_notification"] = _segment_notification("proceed_with_caution")

        updated_segments.append(updated)

    return _build_profile(
        text=str(local_profile["verification_text"] or ""),
        translated_text=str(local_profile["normalized_verification_text"] or ""),
        segments=updated_segments,
        method="local_rules_with_openai_advice",
        status="ok",
        error=None,
        openai_profile=openai_profile,
    )


@traced('text.profile', dependency=False)
def profile_content(
    text: str,
    translated_text: Optional[str] = None,
    use_ai: Optional[bool] = None,
) -> Dict[str, object]:
    """
    Profiles post content and returns a route before claim extraction.

    use_ai=False is useful for deterministic tests. By default, OpenAI is used
    only for ambiguous or mixed local profiles when an API key is configured.
    """
    if translated_text is not None:
        translated_text = sanitize_translation(text, translated_text)
    local_profile = _local_profile(text, translated_text)

    if use_ai is False or not _needs_openai_profile(local_profile):
        if use_ai is not False:
            local_profile["openai_profile"] = {
                "used": False,
                "status": "not_needed",
                "error": None,
                "result": None,
            }
        return local_profile

    openai_profile = _request_openai_profile(text, translated_text, local_profile)
    local_profile["openai_profile"] = openai_profile

    if openai_profile["status"] != "ok":
        return local_profile

    return _merge_openai_segment_advice(local_profile, openai_profile)
