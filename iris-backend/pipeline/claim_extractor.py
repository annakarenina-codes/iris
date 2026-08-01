"""
Claim extraction for IRIS Week 4.

OpenAI is used when configured. If the API key, SDK, or request is unavailable,
IRIS falls back to a conservative sentence splitter so the rest of the pipeline
can still run.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from dotenv import load_dotenv


load_dotenv()

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_CLAIMS = 5
OPINION_MARKERS = [
    "delikado",
    "fake news",
    "kawawa",
    "kadiliman",
    "panloloko",
    "pagbabayaran",
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
    "dumating",
    "makikita",
    "nagpasya",
    "inatasan",
    "pinalitan",
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


def _split_segments(text: str) -> List[str]:
    parts = re.split(r"(?:\n+|;\s*|(?<=[.!?])\s+)", text)
    segments = []

    for part in parts:
        segment = _normalize_claim(part)
        if segment:
            segments.append(segment)

    return segments


def _contains_any(text: str, markers: List[str]) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in markers)


def _has_factual_signal(text: str) -> bool:
    return bool(re.search(r"\b\d+\b", text)) or _contains_any(text, FACTUAL_MARKERS)


def _segment_type(text: str) -> str:
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


def _fallback_extract_claims(text: str, translated_text: Optional[str] = None) -> List[Dict[str, object]]:
    source_text = translated_text or text
    segments = _split_segments(source_text)
    claims = []
    last_subject = None

    for segment in segments:
        segment_type = _segment_type(segment)

        if segment_type == "factual_claim":
            claim = _claim_from_segment(segment, last_subject)
            claims.append(claim)
            last_subject = _infer_subject(claim) or last_subject
        elif "fugitive from justice" in segment.lower() and last_subject:
            claims.append(f"{last_subject} is a fugitive from justice.")

        if len(claims) >= MAX_CLAIMS:
            break

    if not claims and _normalize_claim(source_text) and _segment_type(source_text) == "factual_claim":
        claims = [_normalize_claim(source_text)]

    return [
        {
            "claim_id": index,
            "claim_text": claim,
            "normalized_claim": claim,
            "claim_type": "factual_claim",
            "risk_tags": _risk_tags(claim),
        }
        for index, claim in enumerate(claims, start=1)
    ]


def _fallback_ignored_segments(text: str, translated_text: Optional[str] = None) -> List[Dict[str, object]]:
    source_text = translated_text or text
    ignored = []

    for segment in _split_segments(source_text):
        segment_type = _segment_type(segment)

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

    for index, item in enumerate(raw_claims[:MAX_CLAIMS], start=1):
        if isinstance(item, str):
            original_text = _normalize_claim(item)
            normalized_claim = original_text
        else:
            original_text = _normalize_claim(str(item.get("claim_text", "")))
            normalized_claim = _normalize_claim(str(item.get("normalized_claim", original_text)))
            claim_type = str(item.get("claim_type", "factual_claim"))

        if not normalized_claim:
            continue

        if claim_type != "factual_claim":
            continue

        claims.append({
            "claim_id": index,
            "claim_text": original_text or normalized_claim,
            "normalized_claim": normalized_claim,
            "claim_type": "factual_claim",
            "risk_tags": _risk_tags(normalized_claim),
        })

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


def extract_claims(text: str, translated_text: Optional[str] = None) -> Dict[str, object]:
    """
    Extracts factual claims from a post.

    Returns a stable dictionary with extraction status and a numbered claim list.
    """
    fallback_claims = _fallback_extract_claims(text, translated_text)
    fallback_ignored = _fallback_ignored_segments(text, translated_text)

    if OpenAI is None:
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
        "Extract checkable factual claims from messy Philippine social media posts. "
        "Do not reject the whole post because it contains opinion, insults, fear, "
        "support language, or calls to action. Separate those into ignored_segments. "
        "Return JSON only with this shape: "
        '{"claims":[{"claim_text":"original factual claim","normalized_claim":"clear English factual claim","claim_type":"factual_claim"}],'
        '"ignored_segments":[{"text":"opinion or demand","segment_type":"opinion|recommendation|uncheckable"}]}. '
        f"Return at most {MAX_CLAIMS} factual claims. Extract criminal allegations, "
        "public-official claims, event-attendance claims, and disaster-response claims "
        "when they are stated as facts. Do not include opinions, slogans, insults, "
        "predictions, or demands as claims."
    )
    user_content = (
        f"Original post:\n{text}\n\n"
        f"Translated text if available:\n{translated_text or text}"
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
        )
        content = response.choices[0].message.content or "{}"
        claims = _parse_claim_response(content)
        ignored_segments = _parse_ignored_segments(content)
    except Exception as error:
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

    if not claims:
        return {
            "status": "empty_ai_result",
            "method": "local_sentence_split",
            "error": "OpenAI did not return usable claims.",
            "claims": fallback_claims,
            "ignored_segments": fallback_ignored,
            "post_type": _post_type(fallback_claims, fallback_ignored),
            "contains_opinion": _contains_segment_type(fallback_ignored, "opinion"),
            "contains_recommendation": _contains_segment_type(fallback_ignored, "recommendation"),
        }

    return {
        "status": "ok",
        "method": "openai",
        "error": None,
        "claims": claims,
        "ignored_segments": ignored_segments,
        "post_type": _post_type(claims, ignored_segments),
        "contains_opinion": _contains_segment_type(ignored_segments, "opinion"),
        "contains_recommendation": _contains_segment_type(ignored_segments, "recommendation"),
    }
