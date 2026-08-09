import logging
import re
import time
import uuid
from urllib.parse import urlparse

from flask import Flask, request, jsonify
from pipeline.cache import get_cached_verdict, hash_claim, save_cached_verdict
from pipeline.claim_extractor import extract_claims
from pipeline.content_profiler import profile_content
from pipeline.keyword_fallback import keyword_overlap_verdict
from pipeline.language_detector import detect_language
from pipeline.ocr import (
    MAX_IMAGE_BYTES,
    decode_base64_image,
    extract_text_from_image,
    validate_image_bytes,
)
from pipeline.openai_fallback import refine_with_openai_rag
from pipeline.opinion_filter import is_opinion
from pipeline.political_checker import flag_political
from pipeline.search import search_and_extract
from pipeline.translator import translate_to_english
from pipeline.verdict_generator import generate_verdict

app = Flask(__name__)
app.json.sort_keys = False
logging.basicConfig(level=logging.INFO)
RESULT_CACHE_VERSION = "week6-retrieval-query-v2"
POSITIVE_VERDICTS = {"Verified", "Partially Verified"}
ATTRIBUTED_CLAIM_TYPE = "attributed_statement"
EVIDENCE_STOPWORDS = {
    "about",
    "after",
    "also",
    "ang",
    "and",
    "are",
    "because",
    "between",
    "but",
    "citing",
    "direct",
    "from",
    "has",
    "have",
    "into",
    "not",
    "the",
    "that",
    "this",
    "was",
    "were",
    "with",
}


class RequestTimings:
    """Collects per-request backend timing data for IRIS calibration."""

    def __init__(self, request_type):
        self.request_id = uuid.uuid4().hex[:8]
        self.request_type = request_type
        self.started_at = time.perf_counter()
        self.stages = []
        self.finished = False

    def record(self, stage, started_at, status="ok", error=None):
        duration_seconds = time.perf_counter() - started_at
        entry = {
            "stage": stage,
            "duration_seconds": round(duration_seconds, 4),
            "status": status,
        }
        if error:
            entry["error"] = error

        self.stages.append(entry)
        app.logger.info(
            "[TIMING] request=%s type=%s stage=%s status=%s duration=%.2fs%s",
            self.request_id,
            self.request_type,
            stage,
            status,
            duration_seconds,
            f" error={error}" if error else "",
        )

    def finish(self, stage="request.total"):
        if self.finished:
            return

        self.finished = True
        entry = {
            "stage": stage,
            "duration_seconds": round(time.perf_counter() - self.started_at, 4),
            "status": "ok",
        }
        self.stages.append(entry)
        app.logger.info(
            "[TIMING] request=%s type=%s stage=%s status=ok duration=%.2fs",
            self.request_id,
            self.request_type,
            stage,
            entry["duration_seconds"],
        )

    def as_debug_payload(self):
        return {
            "request_id": self.request_id,
            "request_type": self.request_type,
            "stages": self.stages,
        }


def timed_stage(timings, stage, fn):
    if timings is None:
        return fn()

    started_at = time.perf_counter()
    try:
        result = fn()
    except Exception as error:
        timings.record(stage, started_at, status="error", error=type(error).__name__)
        raise

    timings.record(stage, started_at)
    return result


def finalize_response(response, debug_enabled, timings, total_stage):
    if timings is None:
        return response

    timings.finish(total_stage)
    if debug_enabled:
        response.setdefault("debug", {})
        response["debug"]["timings"] = timings.as_debug_payload()

    return response

def build_response(
    base_response,
    debug_enabled,
    opinion_result,
    political_result,
    content_profile=None,
):
    """
    Keeps normal API responses clean, but allows detailed matching info when
    Postman sends: { "text": "...", "debug": true }
    """
    if debug_enabled:
        base_response["debug"] = {
            "opinion_analysis": opinion_result,
            "political_analysis": political_result
        }

        if content_profile is not None:
            base_response["debug"]["content_profile"] = content_profile

    return base_response

def combine_ignored_segments(content_profile, claim_extraction=None):
    """Combines profiler skips with extractor skips without duplicating text."""
    combined = []
    seen = set()

    for segment in content_profile.get("ignored_segments", []):
        key = (segment.get("text"), segment.get("segment_type"))
        if key not in seen:
            combined.append(segment)
            seen.add(key)

    if claim_extraction:
        for segment in claim_extraction.get("ignored_segments", []):
            key = (segment.get("text"), segment.get("segment_type"))
            if key not in seen:
                combined.append(segment)
                seen.add(key)

    return combined

def build_profiler_stop_response(
    text,
    translated,
    language,
    debug_enabled,
    opinion_result,
    political_result,
    content_profile,
):
    """Builds a clean response when the profiler stops verification."""
    route = content_profile["recommended_route"]
    politically_sensitive = political_result["politically_sensitive"]
    flags = ["politically_sensitive"] if politically_sensitive else []
    verdict = "Opinion Detected" if route == "stop_opinion_detected" else "No Checkable Claims"

    response = build_response({
        "verdict": verdict,
        "message": content_profile["user_notification"],
        "original_text": text,
        "translated_text": translated,
        "detected_language": language,
        "politically_sensitive": politically_sensitive,
        "flags": flags,
        "claim_count": 0,
        "claim_extraction_status": "not_run_content_profiler",
        "post_type": content_profile["post_type"],
        "content_profile_status": content_profile["status"],
        "content_profile_route": route,
        "contains_opinion": content_profile["contains_opinion"] or opinion_result["is_opinion"],
        "contains_recommendation": content_profile["contains_recommendation"],
        "contains_forecast_or_projection": content_profile["contains_forecast_or_projection"],
        "contains_satire_or_humor": content_profile["contains_satire_or_humor"],
        "contains_quote": content_profile["contains_quote"],
        "ignored_segments": combine_ignored_segments(content_profile),
    }, debug_enabled, opinion_result, political_result, content_profile)

    return response

def summarize_sources(source_summary, articles):
    """Groups article links by source for Postman and the future UI."""
    grouped_sources = []

    for source in source_summary:
        source_articles = [
            {
                "title": article["title"],
                "url": article["url"],
                "status": article["status"],
                "word_count": article["word_count"],
                "error": article["error"],
            }
            for article in articles
            if article["source"] == source["source"]
        ]

        grouped_sources.append({
            "source": source["source"],
            "results_found": source["results_found"],
            "articles_checked": source["articles_checked"],
            "articles_extracted": source["articles_extracted"],
            "articles": source_articles,
        })

    return grouped_sources


def is_valid_source_url(url):
    """Returns True only for browser-openable evidence URLs."""
    if not isinstance(url, str):
        return False

    stripped_url = url.strip()
    if not stripped_url:
        return False

    try:
        parsed_url = urlparse(stripped_url)
    except ValueError:
        return False

    return parsed_url.scheme in {"http", "https"} and bool(parsed_url.netloc)


def normalize_evidence_url(url):
    """Normalizes source URLs for deduping without changing the public URL."""
    if not is_valid_source_url(url):
        return ""

    parsed_url = urlparse(url.strip())
    return parsed_url._replace(fragment="").geturl().rstrip("/").lower()


def compact_evidence_source(article, evidence_method="semantic_similarity"):
    """Builds the public evidence-source object shown by the API/UI."""
    if not article or not is_valid_source_url(article.get("url")):
        return None

    status = article.get("status")
    try:
        word_count = int(article.get("word_count") or 0)
    except (TypeError, ValueError):
        word_count = 0

    if status != "extracted" or word_count <= 0:
        return None

    source = {
        "source": article.get("source") or "Approved source",
        "title": article.get("title") or article.get("url"),
        "url": article.get("url").strip(),
        "status": status,
        "word_count": word_count,
        "evidence_method": evidence_method,
    }

    if article.get("similarity_score") is not None:
        source["similarity_score"] = article.get("similarity_score")

    return source


def find_extracted_article_by_url(articles, url):
    """Finds the fetched article record for a URL returned by a fallback."""
    normalized_url = normalize_evidence_url(url)
    if not normalized_url:
        return None

    for article in articles:
        if normalize_evidence_url(article.get("url")) == normalized_url:
            return article

    return None


def merge_scored_article(scored_article, articles):
    """Combines scorer metadata with the fetched article text record."""
    full_article = find_extracted_article_by_url(articles, scored_article.get("url"))
    if not full_article:
        return scored_article

    merged = dict(full_article)
    merged.update({
        key: value
        for key, value in scored_article.items()
        if key not in {"text", "description", "error"}
    })
    return merged


def evidence_text(article):
    """Combines article fields used for strict attribution anchor checks."""
    return " ".join([
        str(article.get("title") or ""),
        str(article.get("description") or ""),
        str(article.get("url") or ""),
        str(article.get("text") or ""),
    ])


def evidence_terms(text):
    """Extracts useful lowercase terms for phrase/statement matching."""
    terms = []
    for term in re.findall(r"[a-z0-9]+", str(text).lower()):
        if term in EVIDENCE_STOPWORDS:
            continue
        if len(term) < 3 and not term.isdigit():
            continue
        terms.append(term)

    return terms


def phrase_is_covered(phrase, text, text_terms=None):
    """Checks whether a required attribution phrase appears in evidence."""
    if not phrase:
        return True

    normalized_phrase = " ".join(str(phrase).lower().split())
    normalized_text = " ".join(str(text).lower().split())
    if normalized_phrase and normalized_phrase in normalized_text:
        return True

    required_terms = evidence_terms(phrase)
    if not required_terms:
        return True

    text_terms = text_terms or set(evidence_terms(text))
    return all(term in text_terms for term in required_terms)


def speaker_is_covered(speaker, text, text_terms):
    """Requires named attribution evidence, not just generic topic overlap."""
    if not speaker:
        return False

    if phrase_is_covered(speaker, text, text_terms):
        return True

    speaker_terms = evidence_terms(speaker)
    if not speaker_terms:
        return False

    last_name = speaker_terms[-1]
    return last_name in text_terms


def statement_is_covered(statement, text_terms):
    """Requires a minimum amount of statement-specific evidence terms."""
    statement_terms = []
    seen = set()

    for term in evidence_terms(statement):
        if term in seen:
            continue

        seen.add(term)
        statement_terms.append(term)

    if not statement_terms:
        return False

    matches = [term for term in statement_terms if term in text_terms]
    required_matches = min(4, max(2, len(statement_terms) // 3))
    return len(matches) >= required_matches


def attribution_evidence_gate(article, claim):
    """
    Verifies that an evidence article supports the attribution, not only topic.

    For attributed claims, a source must mention the named speaker and the
    source/program/date anchors when those anchors are part of the claim.
    """
    if claim.get("claim_type") != ATTRIBUTED_CLAIM_TYPE:
        return {
            "matches": True,
            "missing": [],
        }

    attribution = claim.get("attribution") or {}
    article_text = evidence_text(article)
    text_terms = set(evidence_terms(article_text))
    missing = []

    if not speaker_is_covered(attribution.get("speaker"), article_text, text_terms):
        missing.append("speaker")

    for key in ["source", "program", "date"]:
        value = attribution.get(key)
        if value and not phrase_is_covered(value, article_text, text_terms):
            missing.append(key)

    if not statement_is_covered(attribution.get("statement") or claim.get("normalized_claim"), text_terms):
        missing.append("statement")

    return {
        "matches": not missing,
        "missing": missing,
    }


def unique_evidence_sources(candidates):
    """Dedupes evidence links while preserving ranking/order."""
    evidence_sources = []
    seen_urls = set()

    for candidate in candidates:
        normalized_url = normalize_evidence_url(candidate.get("url") if candidate else None)
        if not normalized_url or normalized_url in seen_urls:
            continue

        evidence_sources.append(candidate)
        seen_urls.add(normalized_url)

    return evidence_sources


def evidence_sources_from_verdict(verdict_result, articles, claim):
    """Returns the semantic evidence links that met the support threshold."""
    candidates = []
    for article in verdict_result.get("supporting_sources") or []:
        merged_article = merge_scored_article(article, articles)
        gate = attribution_evidence_gate(merged_article, claim)
        if not gate["matches"]:
            continue

        source = compact_evidence_source(merged_article)
        if source:
            if claim.get("claim_type") == ATTRIBUTED_CLAIM_TYPE:
                source["attribution_match"] = {
                    "speaker": True,
                    "source": bool((claim.get("attribution") or {}).get("source")),
                    "program": bool((claim.get("attribution") or {}).get("program")),
                    "date": bool((claim.get("attribution") or {}).get("date")),
                    "statement": True,
                }
            candidates.append(source)

    return unique_evidence_sources(candidates)


def evidence_sources_from_openai_fallback(openai_fallback, articles, claim):
    """Maps OpenAI-selected supporting URLs back to fetched article records."""
    result = openai_fallback.get("result") or {}
    supporting_urls = result.get("supporting_urls") or []
    candidates = []

    for url in supporting_urls:
        article = find_extracted_article_by_url(articles, url)
        if article and not attribution_evidence_gate(article, claim)["matches"]:
            continue

        source = compact_evidence_source(article, "openai_rag")
        if source:
            candidates.append(source)

    return unique_evidence_sources(candidates)


def evidence_sources_from_keyword_fallback(keyword_fallback, articles, claim):
    """Maps the local fallback's best source back to fetched article evidence."""
    if not keyword_fallback:
        return []

    keyword_source = keyword_fallback.get("primary_keyword_source") or {}
    article = find_extracted_article_by_url(articles, keyword_source.get("url"))
    if article and not attribution_evidence_gate(article, claim)["matches"]:
        return []

    source = compact_evidence_source(article, "keyword_overlap")

    return [source] if source else []


def build_public_evidence_sources(final_verdict, verdict_result, fallback_result, articles, claim):
    """
    Produces the only source list that should be shown as evidence.

    Search-result links and failed/skipped extraction links stay out of this
    list so IRIS never presents unverified URLs as proof.
    """
    if final_verdict not in POSITIVE_VERDICTS:
        return []

    semantic_sources = evidence_sources_from_verdict(verdict_result, articles, claim)
    if semantic_sources:
        return semantic_sources

    openai_sources = evidence_sources_from_openai_fallback(
        fallback_result["openai_fallback"],
        articles,
        claim,
    )
    if openai_sources:
        return openai_sources

    return evidence_sources_from_keyword_fallback(
        fallback_result["keyword_fallback"],
        articles,
        claim,
    )


def evidence_source_count(evidence_sources):
    """Counts unique approved outlets represented in public evidence links."""
    source_names = {
        source.get("source") or source.get("url")
        for source in evidence_sources
        if source
    }
    return len(source_names)

def get_search_status(search_result):
    """Creates a short status for the user-facing API response."""
    statuses = []
    for search in search_result["search"]["searches"]:
        for report in search["source_reports"]:
            statuses.append(report["status"])

    if "missing_api_key" in statuses:
        return {
            "verdict": "Search Not Configured",
            "status": "missing_api_key",
            "message": "Brave Search is not configured yet. Add BRAVE_API_KEY to .env."
        }

    if statuses and all(status == "error" for status in statuses):
        return {
            "verdict": "Search Failed",
            "status": "error",
            "message": "IRIS could not reach the approved sources through Brave Search."
        }

    if search_result["total_search_results"] == 0:
        return {
            "verdict": "No Search Results",
            "status": "no_results",
            "message": "IRIS searched the approved sources but found no matching results."
        }

    return {
        "verdict": "Search Complete",
        "status": "ok",
        "message": "IRIS searched the approved sources and extracted readable article text where possible."
    }

def get_claim_flags(claim_text):
    political_result = flag_political(claim_text)
    politically_sensitive = political_result["politically_sensitive"]

    return {
        "political_result": political_result,
        "politically_sensitive": politically_sensitive,
        "flags": ["politically_sensitive"] if politically_sensitive else [],
    }


def contextualize_attribution_message(claim, verdict, message):
    if claim.get("claim_type") != "attributed_statement":
        return message

    attribution = claim.get("attribution") or {}
    speaker = attribution.get("speaker") or "the named speaker"
    source = attribution.get("source")
    program = attribution.get("program")
    date = attribution.get("date")
    context_parts = []

    if source:
        context_parts.append(str(source))
    if program:
        context_parts.append(f'"{program}"')
    if date:
        context_parts.append(str(date))

    context_phrase = f" with {' / '.join(context_parts)} attribution" if context_parts else ""

    if verdict == "Verified":
        return (
            f"Retrieved evidence supports that {speaker} made this statement{context_phrase}. "
            "This verifies the attribution, not the underlying claim by itself."
        )

    if verdict == "Partially Verified":
        return (
            f"Retrieved evidence is related to {speaker}'s statement, but IRIS "
            "did not find enough evidence to fully verify the attribution."
        )

    if verdict == "Not Found":
        return (
            f"IRIS did not find enough approved-source evidence confirming that "
            f"{speaker} made this statement{context_phrase}."
        )

    return message


def apply_low_confidence_fallback(
    claim_text,
    articles,
    verdict_result,
    timings=None,
    stage_prefix="",
):
    """Runs OpenAI RAG first, then local keyword overlap if OpenAI cannot run."""
    openai_result = timed_stage(
        timings,
        f"{stage_prefix}openai_rag_fallback",
        lambda: refine_with_openai_rag(claim_text, articles, verdict_result),
    )
    keyword_result = None
    final_verdict = verdict_result["verdict"]
    final_message = verdict_result["reason"]

    if openai_result["status"] == "ok" and openai_result["result"]:
        final_verdict = openai_result["result"]["verdict"]
        final_message = openai_result["result"]["reason"]
    elif openai_result["status"] not in ["not_needed", "no_evidence"]:
        keyword_result = timed_stage(
            timings,
            f"{stage_prefix}keyword_overlap_fallback",
            lambda: keyword_overlap_verdict(claim_text, articles),
        )
        final_verdict = keyword_result["verdict"]
        final_message = keyword_result["reason"]

    return {
        "verdict": final_verdict,
        "message": final_message,
        "openai_fallback": openai_result,
        "keyword_fallback": keyword_result,
    }

def verify_claim(claim, language, timings=None):
    """Runs search, scoring, fallback, and caching for one extracted claim."""
    normalized_claim = claim["normalized_claim"]
    retrieval_query = claim.get("search_query") or normalized_claim
    claim_id = claim.get("claim_id", "unknown")
    stage_prefix = f"claim_{claim_id}."
    claim_hash = timed_stage(
        timings,
        f"{stage_prefix}hash_claim",
        lambda: hash_claim(normalized_claim),
    )
    cached_result = timed_stage(
        timings,
        f"{stage_prefix}cache_lookup",
        lambda: get_cached_verdict(claim_hash),
    )

    if cached_result and cached_result.get("cache_version") == RESULT_CACHE_VERSION:
        cached_result["claim_id"] = claim["claim_id"]
        cached_result["claim_text"] = claim["claim_text"]
        cached_result["cache_hit"] = True
        return cached_result

    claim_flags = timed_stage(
        timings,
        f"{stage_prefix}political_flags",
        lambda: get_claim_flags(normalized_claim),
    )
    search_result = timed_stage(
        timings,
        f"{stage_prefix}search_and_extract",
        lambda: search_and_extract(
            primary_query=retrieval_query,
            backup_query=(
                normalized_claim
                if retrieval_query.strip().lower() != normalized_claim.strip().lower()
                else claim["claim_text"] if language in ["tagalog", "taglish"] else None
            )
        ),
    )
    search_status = timed_stage(
        timings,
        f"{stage_prefix}search_status",
        lambda: get_search_status(search_result),
    )
    verdict_result = timed_stage(
        timings,
        f"{stage_prefix}generate_verdict",
        lambda: generate_verdict(normalized_claim, search_result["articles"]),
    )

    final_verdict = verdict_result["verdict"]
    final_message = verdict_result["reason"]
    fallback_result = {
        "openai_fallback": {
            "used": False,
            "status": "not_run",
            "error": None,
            "result": None,
        },
        "keyword_fallback": None,
    }

    if search_status["status"] != "ok":
        final_verdict = search_status["verdict"]
        final_message = search_status["message"]
    else:
        fallback_result = timed_stage(
            timings,
            f"{stage_prefix}fallback_total",
            lambda: apply_low_confidence_fallback(
                normalized_claim,
                search_result["articles"],
                verdict_result,
                timings,
                stage_prefix,
            ),
        )
        final_verdict = fallback_result["verdict"]
        final_message = fallback_result["message"]

    evidence_sources = timed_stage(
        timings,
        f"{stage_prefix}public_evidence_sources",
        lambda: build_public_evidence_sources(
            final_verdict,
            verdict_result,
            fallback_result,
            search_result["articles"],
            claim,
        ),
    )

    if final_verdict in POSITIVE_VERDICTS and not evidence_sources:
        final_verdict = "Not Found"
        final_message = (
            "IRIS found related material, but no valid extracted source link "
            "could be shown as evidence for this claim."
        )

    final_message = contextualize_attribution_message(
        claim,
        final_verdict,
        final_message,
    )

    claim_result = {
        "claim_id": claim["claim_id"],
        "claim_text": claim["claim_text"],
        "normalized_claim": normalized_claim,
        "claim_type": claim.get("claim_type", "factual_claim"),
        "verification_focus": claim.get("verification_focus", claim.get("claim_type", "factual_claim")),
        "attribution": claim.get("attribution"),
        "search_query": retrieval_query,
        "risk_tags": claim.get("risk_tags", []),
        "claim_hash": claim_hash,
        "cache_version": RESULT_CACHE_VERSION,
        "verdict": final_verdict,
        "message": final_message,
        "politically_sensitive": claim_flags["politically_sensitive"],
        "flags": claim_flags["flags"],
        "cache_hit": False,
        "corroboration_count": evidence_source_count(evidence_sources),
        "primary_evidence": evidence_sources[0] if evidence_sources else None,
        "supporting_sources": evidence_sources,
        "search_status": search_status["status"],
        "total_search_results": search_result["total_search_results"],
        "searched_articles": search_result["searched_articles"],
        "extracted_articles": search_result["extracted_articles"],
        "source_summary": search_result["source_summary"],
        "sources": evidence_sources,
        "evidence_sources": evidence_sources,
        "evidence_policy": (
            "Only valid http/https links from extracted evidence used for the "
            "verdict are shown. Attributed claims also require speaker/source/"
            "program/date anchors when those anchors are part of the claim."
        ),
        "fallback": {
            "openai": fallback_result["openai_fallback"],
            "keyword_overlap": fallback_result["keyword_fallback"],
        },
    }

    if search_status["status"] == "ok":
        timed_stage(
            timings,
            f"{stage_prefix}cache_save",
            lambda: save_cached_verdict(claim_hash, normalized_claim, claim_result),
        )

    return claim_result

def build_overall_verdict(claim_results):
    if not claim_results:
        return {
            "verdict": "No Checkable Claims",
            "message": "IRIS did not find factual claims that can be checked against sources.",
        }

    if len(claim_results) == 1:
        return {
            "verdict": claim_results[0]["verdict"],
            "message": claim_results[0]["message"],
        }

    return {
        "verdict": "Multiple Claims Checked",
        "message": f"IRIS checked {len(claim_results)} extracted claims individually.",
    }

def add_single_claim_compatibility_fields(response, claim_results):
    """Keeps the Week 3 response shape for one-claim requests."""
    if len(claim_results) != 1:
        return response

    claim_result = claim_results[0]
    response.update({
        "corroboration_count": claim_result["corroboration_count"],
        "primary_evidence": claim_result["primary_evidence"],
        "supporting_sources": claim_result["supporting_sources"],
        "search_status": claim_result["search_status"],
        "total_search_results": claim_result["total_search_results"],
        "searched_articles": claim_result["searched_articles"],
        "extracted_articles": claim_result["extracted_articles"],
        "source_summary": claim_result["source_summary"],
        "sources": claim_result["sources"],
        "evidence_sources": claim_result["evidence_sources"],
        "evidence_policy": claim_result["evidence_policy"],
    })

    return response

def build_ocr_response_fields(ocr_result):
    """Returns the public OCR fields included by /verify-image."""
    return {
        "input_type": "image",
        "ocr_status": ocr_result["status"],
        "ocr_text": ocr_result["text"],
        "ocr_confidence": ocr_result["confidence"],
        "ocr_word_count": ocr_result["word_count"],
        "ocr_low_confidence": ocr_result["low_confidence"],
        "ocr_warnings": ocr_result["warnings"],
        "ocr_regions": ocr_result["regions"],
        "image_authenticity_checked": False,
    }

def add_ocr_response_fields(response, ocr_result, debug_enabled):
    response.update(build_ocr_response_fields(ocr_result))

    if debug_enabled:
        response.setdefault("debug", {})
        response["debug"]["ocr"] = ocr_result

    return response

def _truthy(value):
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def _get_image_bytes_from_request(data):
    if request.files and "image" in request.files:
        image_file = request.files["image"]
        image_bytes = image_file.read(MAX_IMAGE_BYTES + 1)
        validation = validate_image_bytes(image_bytes)

        if validation["status"] != "ok":
            return validation

        validation["image_bytes"] = image_bytes
        return validation

    data = data or {}
    for key in ["image_base64", "base64_image", "image"]:
        if data.get(key):
            return decode_base64_image(data[key])

    return {
        "status": "missing_image",
        "message": "Provide an image file or a base64 image field.",
        "http_status": 400,
    }

def _ocr_error_http_status(ocr_result):
    if ocr_result["status"] == "missing_dependency":
        return 503

    if ocr_result["status"] == "image_too_large":
        return 413

    if ocr_result["status"] in ["missing_image", "unsupported_image_type", "corrupt_image"]:
        return 400

    if ocr_result["status"] == "no_text":
        return 422

    return 500

def build_ocr_stop_response(ocr_result, debug_enabled):
    status = ocr_result["status"]

    if status == "missing_dependency":
        verdict = "OCR Unavailable"
        message = "OCR dependencies are not installed yet, so IRIS could not read the image."
    elif status == "no_text":
        verdict = "No Text Extracted"
        message = "IRIS could not extract readable text from the submitted image."
    else:
        verdict = "OCR Failed"
        message = ocr_result.get("error") or "IRIS could not process the submitted image."

    response = {
        "verdict": verdict,
        "message": message,
    }
    return add_ocr_response_fields(response, ocr_result, debug_enabled)

def verify_text_payload(text, debug_enabled=False, timings=None):
    owns_timings = timings is None
    timings = timings or RequestTimings("verify_text")

    def complete_response(response):
        if owns_timings:
            return finalize_response(
                response,
                debug_enabled,
                timings,
                "verify_text.total",
            )

        return response

    # Step 1: Detect language
    language = timed_stage(
        timings,
        "text.detect_language",
        lambda: detect_language(text),
    )

    # Step 2: Translate if needed
    translated = timed_stage(
        timings,
        "text.translate_to_english",
        lambda: translate_to_english(text, language),
    )

    # Step 3: Profile content before claim extraction and retrieval.
    content_profile = timed_stage(
        timings,
        "text.profile_content",
        lambda: profile_content(text, translated),
    )
    opinion_result = timed_stage(
        timings,
        "text.opinion_filter",
        lambda: is_opinion(text),
    )
    political_result = timed_stage(
        timings,
        "text.political_check",
        lambda: flag_political(text),
    )
    politically_sensitive = political_result["politically_sensitive"]

    if not content_profile["eligible_for_verification"]:
        response = build_profiler_stop_response(
            text,
            translated,
            language,
            debug_enabled,
            opinion_result,
            political_result,
            content_profile,
        )
        return complete_response(response)

    # Step 4: Extract claims only from profiler-approved factual text.
    verification_text = content_profile["verification_text"]
    normalized_verification_text = content_profile["normalized_verification_text"]
    claim_extraction = timed_stage(
        timings,
        "text.extract_claims",
        lambda: extract_claims(verification_text, normalized_verification_text),
    )

    if not claim_extraction["claims"]:
        flags = ["politically_sensitive"] if politically_sensitive else []
        verdict = "Opinion Detected" if opinion_result["is_opinion"] else "No Checkable Claims"
        message = (
            "This appears to be an opinion, so IRIS did not perform fact-checking."
            if verdict == "Opinion Detected"
            else "IRIS did not find factual claims that can be checked against sources."
        )

        response = build_response({
            "verdict": verdict,
            "message": message,
            "original_text": text,
            "translated_text": translated,
            "detected_language": language,
            "politically_sensitive": politically_sensitive,
            "flags": flags,
            "claim_count": 0,
            "claim_extraction_status": claim_extraction["status"],
            "post_type": content_profile["post_type"],
            "content_profile_status": content_profile["status"],
            "content_profile_route": content_profile["recommended_route"],
            "contains_opinion": (
                content_profile["contains_opinion"]
                or claim_extraction["contains_opinion"]
                or opinion_result["is_opinion"]
            ),
            "contains_recommendation": (
                content_profile["contains_recommendation"]
                or claim_extraction["contains_recommendation"]
            ),
            "contains_forecast_or_projection": content_profile["contains_forecast_or_projection"],
            "contains_satire_or_humor": content_profile["contains_satire_or_humor"],
            "contains_quote": content_profile["contains_quote"],
            "ignored_segments": combine_ignored_segments(content_profile, claim_extraction),
        }, debug_enabled, opinion_result, political_result, content_profile)

        if debug_enabled:
            response["debug"]["claim_extraction"] = claim_extraction

        return complete_response(response)

    # Step 5: Verify each extracted factual claim independently.
    claim_results = timed_stage(
        timings,
        "text.verify_claims_total",
        lambda: [
            verify_claim(claim, language, timings)
            for claim in claim_extraction["claims"]
        ],
    )
    overall = build_overall_verdict(claim_results)
    politically_sensitive = any(
        claim_result["politically_sensitive"] for claim_result in claim_results
    ) or political_result["politically_sensitive"]
    flags = ["politically_sensitive"] if politically_sensitive else []

    response = build_response({
        "verdict": overall["verdict"],
        "message": overall["message"],
        "original_text": text,
        "translated_text": translated,
        "detected_language": language,
        "politically_sensitive": politically_sensitive,
        "flags": flags,
        "claim_count": len(claim_results),
        "claim_extraction_status": claim_extraction["status"],
        "post_type": content_profile["post_type"],
        "content_profile_status": content_profile["status"],
        "content_profile_route": content_profile["recommended_route"],
        "contains_opinion": (
            content_profile["contains_opinion"]
            or claim_extraction["contains_opinion"]
            or opinion_result["is_opinion"]
        ),
        "contains_recommendation": (
            content_profile["contains_recommendation"]
            or claim_extraction["contains_recommendation"]
        ),
        "contains_forecast_or_projection": content_profile["contains_forecast_or_projection"],
        "contains_satire_or_humor": content_profile["contains_satire_or_humor"],
        "contains_quote": content_profile["contains_quote"],
        "ignored_segments": combine_ignored_segments(content_profile, claim_extraction),
        "claims": claim_results,
        "searched_sources": "VERA Files + 7 approved Philippine news sources",
    }, debug_enabled, opinion_result, political_result, content_profile)
    response = add_single_claim_compatibility_fields(response, claim_results)

    if debug_enabled:
        response["debug"]["claim_extraction"] = claim_extraction

    return complete_response(response)

@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()

    if not data or 'text' not in data:
        return jsonify({ "error": "No text provided" }), 400

    text = data['text'].strip()
    debug_enabled = bool(data.get("debug", False))

    if not text:
        return jsonify({ "error": "Text cannot be empty" }), 400

    return jsonify(verify_text_payload(text, debug_enabled))

@app.route('/verify-image', methods=['POST'])
def verify_image():
    timings = RequestTimings("verify_image")
    data = request.get_json(silent=True) if request.is_json else {}
    data = data or {}
    debug_enabled = _truthy(data.get("debug")) or _truthy(request.form.get("debug"))
    image_result = timed_stage(
        timings,
        "image.decode_and_validate",
        lambda: _get_image_bytes_from_request(data),
    )

    if image_result["status"] != "ok":
        response = {
            "verdict": "OCR Failed",
            "message": image_result["message"],
            "input_type": "image",
            "ocr_status": image_result["status"],
            "ocr_text": "",
            "ocr_confidence": None,
            "ocr_word_count": 0,
            "ocr_low_confidence": True,
            "ocr_warnings": [image_result["message"]],
            "ocr_regions": [],
            "image_authenticity_checked": False,
        }
        response = finalize_response(
            response,
            debug_enabled,
            timings,
            "verify_image.total",
        )
        return jsonify(response), int(image_result.get("http_status", 400))

    ocr_result = timed_stage(
        timings,
        "image.extract_text_from_image",
        lambda: extract_text_from_image(image_result["image_bytes"]),
    )

    if ocr_result["status"] != "ok" or not ocr_result["text"].strip():
        response = build_ocr_stop_response(ocr_result, debug_enabled)
        response = finalize_response(
            response,
            debug_enabled,
            timings,
            "verify_image.total",
        )
        return jsonify(response), _ocr_error_http_status(ocr_result)

    response = timed_stage(
        timings,
        "image.verify_extracted_text_total",
        lambda: verify_text_payload(ocr_result["text"], debug_enabled, timings),
    )
    response = add_ocr_response_fields(response, ocr_result, debug_enabled)
    response = finalize_response(
        response,
        debug_enabled,
        timings,
        "verify_image.total",
    )
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
