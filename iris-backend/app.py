
from iris_trace.core import traced, event, CURRENT
import logging
import re
import time
import uuid
from urllib.parse import urlparse

import requests
from flask import Flask, request, jsonify
from pipeline.cache import get_cached_verdict, hash_claim, save_cached_verdict
from pipeline.attribution_integrity import (attribution_phrase_match, date_phrase_match,
                                            is_calendar_date, speaker_phrase_match)
from pipeline.evidence_urls import article_url_rejection, is_opinion_url
from pipeline.checkable_claims import only_general_statements
from pipeline.claim_extractor import extract_claims
from pipeline.component_evidence import REFUTED_VERDICT
from pipeline.content_profiler import profile_content
from pipeline.coverage_scope import (OUT_OF_SCOPE_VERDICT, SCRIPTURE_VERDICT, out_of_scope_message,
                                     philippine_scope, scriptural_narrative, scripture_message)
from pipeline.event_retrieval import (
    build_event_search_query,
    mark_quote_derived_claims,
)
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
from pipeline.political_checker import flag_political, flag_claim_political
from pipeline.quote_paraphraser import paraphrase_quote_claim
from pipeline.search import merge_search_results, search_and_extract
from pipeline.search_queries import anchored_query, original_language_query
from pipeline.translator import translate_to_english
from pipeline.verdict_generator import generate_verdict

app = Flask(__name__)
app.json.sort_keys = False
from iris_trace.web import init_app as init_trace
init_trace(app)
logging.basicConfig(level=logging.INFO)
RESULT_CACHE_VERSION = "week7-scripture-dates-v37"
POSITIVE_VERDICTS = {"Verified", "Partially Verified"}
# A verdict that asserts something about the world has to show the source it rests on.
VERDICTS_NEEDING_EVIDENCE = POSITIVE_VERDICTS | {REFUTED_VERDICT}
REVIEW_FAILED_VERDICT = "Review Failed"
REVIEW_FAILED_MESSAGE = (
    "IRIS could not complete the evidence review for this claim, so no verdict was "
    "issued. This is a technical failure, not a finding about the claim. Please retry."
)
ATTRIBUTED_CLAIM_TYPE = "attributed_statement"
# "Facebook post", "viral post", "netizens": where a claim circulated, not an outlet that
# reporting must name. Requiring these words inside news articles rejected every source (C06).
PLATFORM_SOURCE_WORDS = {
    "facebook", "fb", "instagram", "ig", "twitter", "tiktok", "youtube", "messenger",
    "social", "media", "post", "posts", "page", "pages", "online", "viral", "netizen",
    "netizens", "user", "users", "account", "video", "reel", "story", "stories",
}
REMOTE_IMAGE_TIMEOUT_SECONDS = 10
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
        self.request_id = CURRENT.get().id if CURRENT.get() else uuid.uuid4().hex[:8]
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
        event('timing', **entry)
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
        event('timing', **entry)
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
                "extraction_quality": article.get("extraction_quality"),
                "evidence_type": article.get("evidence_type"),
                "evidence_pool": article.get("evidence_pool"),
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
    if not article or article_url_rejection(article.get("url")):
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

    if article.get("extraction_quality"):
        source["extraction_quality"] = article.get("extraction_quality")

    if article.get("evidence_pool"):
        source["evidence_pool"] = article.get("evidence_pool")

    if article.get("evidence_type"):
        source["evidence_type"] = article.get("evidence_type")

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

    return attribution_phrase_match(phrase, text)


def is_platform_reference(value):
    """True for a social-platform or self-referential source such as "Facebook post"."""
    words = {word for word in re.findall(r"[^\W_]+", str(value or "").lower())}
    return bool(words) and words <= PLATFORM_SOURCE_WORDS


def speaker_is_covered(speaker, text, text_terms, source_text=''):
    """Requires named attribution evidence, not just generic topic overlap."""
    if not speaker:
        return False

    # Accepts only the name forms the post itself supplies (nickname, titles), never a new name.
    return speaker_phrase_match(speaker, text, source_text)


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


@traced('claim.attribution_gate', dependency=False)
def attribution_evidence_gate(article, claim, anchors_only=False):
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
    article_text = str(article.get("text") or "")
    text_terms = set(evidence_terms(article_text))
    missing = []
    anchor_checks = {}

    speaker = attribution.get("speaker")
    if not speaker:
        # An unresolved speaker ("the judges") is not evidence of a wrong source: requiring a name
        # IRIS never had rejected every article. The component review still decides attribution.
        anchor_checks["speaker"] = "unresolved_not_required"
    elif speaker_is_covered(speaker, article_text, text_terms, claim.get("evidence_context", "")):
        anchor_checks["speaker"] = "normalized_phrase_match"
    else:
        anchor_checks["speaker"] = "missing_or_unmatched"
        missing.append("speaker")

    for key in ["source", "program"]:
        value = attribution.get(key)
        if key == "source" and is_platform_reference(value):
            anchor_checks[key] = "platform_reference_not_required"
            continue
        matched = phrase_is_covered(value, article_text, text_terms)
        anchor_checks[key] = ("not_required" if not value else
                              "normalized_phrase_match" if matched else "unmatched")
        if value and not matched:
            missing.append(key)

    # A news story rarely reprints the calendar date of the event it reports, so requiring it
    # threw away the coverage as well as the stale article (saved case C06: 13 of 15 articles
    # stated no date at all). An unconfirmed date no longer excludes the article; it caps the
    # verdict at Partially Verified, and a conflicting date is still refused by the component
    # review's event identity, year and occurrence rules.
    claimed_date = attribution.get("date")
    date_confirmed = bool(claimed_date) and date_phrase_match(claimed_date, article_text)
    anchor_checks["date"] = ("not_required" if not claimed_date else
                             "normalized_phrase_match" if date_confirmed else "unconfirmed")

    statement = attribution.get("statement") or claim.get("normalized_claim")
    # Non-reviewed legacy callers may only accept a literal statement match.
    # Paraphrased support is handled by component review, not a lexical cutoff.
    covered = bool(statement) and " ".join(str(statement).lower().split()) in " ".join(article_text.lower().split())
    if not anchors_only and not covered:
        missing.append("statement")

    return {
        "matches": not missing,
        "missing": missing,
        "anchor_checks": anchor_checks,
        "date_confirmed": date_confirmed,
    }


def cap_unconfirmed_date(verdict, message, claim, articles):
    """
    Keeps a claim off Verified while no shown source states the date it asserts.

    The component review caps a verdict when it resolved the claim's time itself. This is the
    same rule applied to the claim's attribution date, so the ceiling does not depend on what
    the review's context extraction happened to capture.
    """
    claimed_date = (claim.get("attribution") or {}).get("date")
    if verdict != "Verified" or not claimed_date:
        return verdict, message
    if not is_calendar_date(claimed_date):
        # "Saturday" or "last week" names no day a source could print, so its absence says
        # nothing. Held-out post H14 lost three correct verdicts this way.
        event('verdict.date_not_calendar', claimed_date=claimed_date)
        return verdict, message
    if any(attribution_evidence_gate(article, claim, anchors_only=True)["date_confirmed"]
           for article in articles):
        return verdict, message
    event('verdict.date_unconfirmed', claimed_date=claimed_date)
    return "Partially Verified", (
        f"{message} No shown source states {claimed_date}, so the date itself is unconfirmed.")


def build_out_of_scope_response(text, translated, language, debug_enabled, opinion_result,
                                political_result, content_profile, scope,
                                verdict=OUT_OF_SCOPE_VERDICT, message=None,
                                route="stop_outside_philippine_coverage"):
    """Tells the reader IRIS does not cover this subject, instead of reporting Not Found."""
    return build_response({
        "verdict": verdict,
        "message": message or out_of_scope_message(scope.get("subject")),
        "original_text": text,
        "translated_text": translated,
        "detected_language": language,
        "politically_sensitive": political_result["politically_sensitive"],
        "flags": [route.replace("stop_", "")]
                 + (["politically_sensitive"] if political_result["politically_sensitive"] else []),
        "claim_count": 0,
        "claim_extraction_status": "not_run_outside_coverage",
        "post_type": content_profile["post_type"],
        "content_profile_status": content_profile["status"],
        "content_profile_route": route,
        "coverage_scope": scope,
        "contains_opinion": content_profile["contains_opinion"] or opinion_result["is_opinion"],
        "contains_recommendation": content_profile["contains_recommendation"],
        "contains_forecast_or_projection": content_profile["contains_forecast_or_projection"],
        "contains_satire_or_humor": content_profile["contains_satire_or_humor"],
        "contains_quote": content_profile["contains_quote"],
        "ignored_segments": combine_ignored_segments(content_profile),
    }, debug_enabled, opinion_result, political_result, content_profile)


def is_opinion_article(article):
    """True when the article is a column or commentary rather than reporting."""
    return bool(article) and (bool(article.get("is_opinion")) or is_opinion_url(article.get("url")))


def opinion_evidence_blocked(article, claim):
    """
    Keeps opinion writing out of the evidence for a factual claim.

    A column argues; it does not report. Saved case B07 supported a factual claim with an
    Inquirer opinion piece and a VERA Files commentary. For an attributed statement the column
    is still admissible, because a claim about what a columnist wrote is proven by the column.
    """
    if claim.get("claim_type") == ATTRIBUTED_CLAIM_TYPE:
        return False
    return is_opinion_article(article)


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


@traced('claim.evidence_gate', dependency=False)
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

@traced('retrieval.status')
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

@traced('claim.political')
def get_claim_flags(claim_text, claim=None):
    political_result = flag_claim_political(claim) if claim else flag_political(claim_text)
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


@traced('claim.fallback')
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
    event('verdict.semantic', verdict=verdict_result.get('verdict'), reason=verdict_result.get('reason'))
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


def build_claim_cache_basis(normalized_claim, claim, scoring_claim, shared_evidence_pool):
    """Keeps quote/event-context cache entries separate from standalone checks."""
    parts = [normalized_claim]
    if claim.get('claim_text'):
        parts.append(f"original_claim:{claim['claim_text']}")
    if claim.get('evidence_context'):
        parts.append(f"source_context:{claim['evidence_context']}")

    if claim.get("is_quote_derived"):
        parts.append("quote_derived:true")

    if scoring_claim and scoring_claim != normalized_claim:
        parts.append(f"scoring_claim:{scoring_claim}")

    if shared_evidence_pool and shared_evidence_pool.get("used"):
        parts.append(f"event_query:{shared_evidence_pool.get('query')}")

    return "\n".join(parts)


def should_build_event_pool(claims, content_profile):
    """Runs shared event retrieval only when it can help a multi-claim post."""
    if not claims:
        return False

    if any(claim.get("is_quote_derived") for claim in claims):
        return True

    return bool(content_profile.get("contains_quote")) and len(claims) > 1


def tag_search_result_articles(search_result, evidence_pool):
    """Copies a search result and tags every article with its pool role."""
    if not search_result:
        return None

    tagged = dict(search_result)
    tagged["articles"] = [
        {
            **article,
            "evidence_pool": article.get("evidence_pool") or evidence_pool,
        }
        for article in search_result.get("articles") or []
    ]
    return tagged


@traced('event.retrieve', dependency=False)
def build_shared_event_evidence_pool(
    text,
    translated_text,
    claims,
    content_profile,
):
    """Searches the broader post event once and returns a reusable pool."""
    if not should_build_event_pool(claims, content_profile):
        return {
            "used": False,
            "status": "not_needed",
            "query": None,
            "search_result": None,
        }

    query = build_event_search_query(
        text=text,
        translated_text=translated_text,
        claims=claims,
    )
    if not query:
        return {
            "used": False,
            "status": "empty_query",
            "query": None,
            "search_result": None,
        }

    search_result = search_and_extract(primary_query=query)
    search_result = tag_search_result_articles(search_result, "event_context")

    return {
        "used": True,
        "status": "ok",
        "query": query,
        "search_result": search_result,
        "total_search_results": search_result["total_search_results"],
        "searched_articles": search_result["searched_articles"],
        "extracted_articles": search_result["extracted_articles"],
        "source_summary": search_result["source_summary"],
    }


def summarize_shared_evidence_pool(shared_evidence_pool):
    """Returns a compact debug-safe summary without full article text."""
    if not shared_evidence_pool:
        return {
            "used": False,
            "status": "not_run",
        }

    search_result = shared_evidence_pool.get("search_result") or {}
    return {
        "used": bool(shared_evidence_pool.get("used")),
        "status": shared_evidence_pool.get("status"),
        "query": shared_evidence_pool.get("query"),
        "total_search_results": shared_evidence_pool.get("total_search_results", 0),
        "searched_articles": shared_evidence_pool.get("searched_articles", 0),
        "extracted_articles": shared_evidence_pool.get("extracted_articles", 0),
        "source_summary": shared_evidence_pool.get("source_summary", []),
        "articles": [
            {
                "source": article.get("source"),
                "title": article.get("title"),
                "url": article.get("url"),
                "status": article.get("status"),
                "word_count": article.get("word_count"),
                "extraction_quality": article.get("extraction_quality"),
                "evidence_type": article.get("evidence_type"),
            }
            for article in search_result.get("articles") or []
        ],
    }


def quote_paraphrase_for_claim(claim, timings, stage_prefix):
    """Returns paraphrase metadata and the claim text to use for scoring."""
    default_result = {
        "used_for_scoring": False,
        "status": "not_needed",
        "method": "not_run",
        "error": None,
        "paraphrase": claim["normalized_claim"],
    }

    if not claim.get("is_quote_derived"):
        event('stage.skipped', stages=['claim.paraphrase'], reason='Claim is not quote derived')
        return default_result

    return timed_stage(
        timings,
        f"{stage_prefix}quote_paraphrase",
        lambda: paraphrase_quote_claim(claim),
    )


@traced('claim.retrieve', dependency=False)
def build_claim_search_result(
    claim,
    language,
    retrieval_query,
    normalized_claim,
    shared_evidence_pool,
):
    """Chooses event-only, claim-only, or claim-plus-event retrieval."""
    event_search_result = (
        shared_evidence_pool.get("search_result")
        if shared_evidence_pool and shared_evidence_pool.get("used")
        else None
    )
    has_event_articles = bool(event_search_result and event_search_result.get("articles"))

    if claim.get("is_quote_derived") and has_event_articles:
        return (
            tag_search_result_articles(event_search_result, "event_context"),
            "event_pool_only",
        )

    claim_search_result = search_and_extract(
        primary_query=retrieval_query,
        backup_query=(
            normalized_claim
            if retrieval_query.strip().lower() != normalized_claim.strip().lower()
            else claim["claim_text"] if language in ["tagalog", "taglish"] else None
        ),
        original_language_query=(
            claim.get("original_language_query") if language in ["tagalog", "taglish"] else None
        ),
        # A picture's claim can lose the very name that finds its fact-check: held-out post
        # H18 kept "EDU MANZANO" in the reading and lost it from the claim, while the fact-check
        # is filed under his name. The sitemap lookup ranks by rare words, so giving it the
        # post's own words costs nothing and finds what the claim cannot.
        fact_check_text=" ".join(part for part in [
            claim.get("claim_text") or normalized_claim,
            claim.get("evidence_context", "") if claim.get("from_image") else ""] if part),
    )

    if has_event_articles:
        return (
            merge_search_results(claim_search_result, event_search_result),
            "claim_search_plus_event_pool",
        )

    return claim_search_result, "claim_search_only"


@traced('claim.process', dependency=False)
def verify_claim(claim, language, timings=None, shared_evidence_pool=None):
    """Runs search, scoring, fallback, and caching for one extracted claim."""
    normalized_claim = claim["normalized_claim"]
    retrieval_query = claim.get("search_query") or normalized_claim
    from pipeline.claim_context import incident_anchor, contextual_search_query, incident_evidence_gate
    context_anchor = incident_anchor(normalized_claim, claim.get('evidence_context', ''))
    retrieval_query = contextual_search_query(retrieval_query, context_anchor)
    # Keep the claim's dates, numbers and short titles that the generated query dropped.
    retrieval_query = anchored_query(retrieval_query, claim.get("claim_text") or normalized_claim)
    claim_id = claim.get("claim_id", "unknown")
    stage_prefix = f"claim_{claim_id}."

    quote_paraphrase = quote_paraphrase_for_claim(
        claim,
        timings,
        stage_prefix,
    )
    scoring_claim = quote_paraphrase.get("paraphrase") or normalized_claim
    cache_basis = build_claim_cache_basis(
        normalized_claim,
        claim,
        scoring_claim,
        shared_evidence_pool,
    )
    claim_hash = timed_stage(
        timings,
        f"{stage_prefix}hash_claim",
        lambda: hash_claim(cache_basis),
    )
    cached_result = timed_stage(
        timings,
        f"{stage_prefix}cache_lookup",
        lambda: get_cached_verdict(claim_hash),
    )

    if cached_result and cached_result.get("cache_version") == RESULT_CACHE_VERSION:
        event('stage.skipped', stages=['claim.retrieve','claim.semantic','claim.fallback','claim.component_review'], reason='Matching cache entry reused')
        event('cache.hit', claim_id=claim['claim_id'], cache_version=cached_result.get('cache_version'), downstream='retrieval and review bypassed')
        cached_result["claim_id"] = claim["claim_id"]
        cached_result["claim_text"] = claim["claim_text"]
        cached_result["is_quote_derived"] = bool(claim.get("is_quote_derived"))
        cached_result["cache_hit"] = True
        return cached_result

    claim_flags = timed_stage(
        timings,
        f"{stage_prefix}political_flags",
        lambda: get_claim_flags(normalized_claim, claim),
    )
    search_result = timed_stage(
        timings,
        f"{stage_prefix}search_and_extract",
        lambda: build_claim_search_result(
            claim,
            language,
            retrieval_query,
            normalized_claim,
            shared_evidence_pool,
        ),
    )
    retrieval_strategy = search_result[1]
    search_result = search_result[0]
    search_status = timed_stage(
        timings,
        f"{stage_prefix}search_status",
        lambda: get_search_status(search_result),
    )
    verdict_result = timed_stage(
        timings,
        f"{stage_prefix}generate_verdict",
        lambda: generate_verdict(scoring_claim, search_result["articles"]),
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
                scoring_claim,
                search_result["articles"],
                verdict_result,
                timings,
                stage_prefix,
            ),
        )
        event('verdict.fallback', before=final_verdict, after=fallback_result.get('verdict'), details=fallback_result)
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

    component_review = None
    review_error = None
    if search_status["status"] == "ok":
        from pipeline.component_evidence import (
            ComponentReviewError,
            require_completed_review,
            review_components,
        )
        eligible = [article for article in search_result["articles"]
                    if compact_evidence_source(article)
                    and article.get("text")
                    and not opinion_evidence_blocked(article, claim)
                    and attribution_evidence_gate(article, claim, anchors_only=True)["matches"]
                    and incident_evidence_gate(article, context_anchor)["matches"]]
        opinion_excluded = [article.get("url") for article in search_result["articles"]
                            if article.get("text") and opinion_evidence_blocked(article, claim)]
        if opinion_excluded:
            event('evidence.opinion_excluded', urls=opinion_excluded, claim_type=claim.get("claim_type"))
        # Most relevant first, so the reviewer's evidence budget holds the best articles.
        relevance = {article["url"]: article["similarity_score"]
                     for article in verdict_result.get("ranked_articles") or []}
        eligible.sort(key=lambda article: -relevance.get(article.get("url"), -1.0))
        event('evidence.incident_gate', anchor=context_anchor, articles=[
            {'url': article.get('url'), **incident_evidence_gate(article, context_anchor)}
            for article in search_result['articles']])
        component_review = timed_stage(
            timings, f"{stage_prefix}component_evidence_review",
            lambda: review_components(claim.get('claim_text') or normalized_claim, eligible,
                                      source_context=claim.get('evidence_context', '')),
        ) if eligible else {"status": "no_evidence", "verdict": "Not Found",
                            "reason": "No valid extracted evidence satisfied the claim's required anchors.",
                            "supporting_urls": [], "components": []}
        try:
            require_completed_review(component_review)
        except ComponentReviewError as error:
            review_error = {"reason_code": error.reason_code, "failed_stage": error.stage,
                            "retryable": True}
        if review_error:
            # A failed review is reported for this claim only; other claims keep their results.
            event('verdict.review_failed', before=final_verdict, after=REVIEW_FAILED_VERDICT,
                  **review_error)
            final_verdict = REVIEW_FAILED_VERDICT
            final_message = REVIEW_FAILED_MESSAGE
            evidence_sources = []
        else:
            event('verdict.component_review', before=final_verdict, after=component_review.get('verdict'), details=component_review)
            final_verdict = component_review["verdict"]
            final_message = component_review["reason"]
            evidence_sources = unique_evidence_sources([
                compact_evidence_source(article, "component_review") for article in eligible
                if article.get("url") in component_review["supporting_urls"]
            ])
            final_verdict, final_message = cap_unconfirmed_date(
                final_verdict, final_message, claim,
                [article for article in eligible
                 if article.get("url") in component_review["supporting_urls"]])

    if final_verdict in VERDICTS_NEEDING_EVIDENCE and not evidence_sources:
        event('verdict.evidence_gate', before=final_verdict, after='Not Found', reason='No valid public evidence')
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
        "attribution_integrity": claim.get("attribution_integrity"),
        "component_review": component_review,
        "review_error": review_error,
        "incident_evidence_audit": [
            {'url': article.get('url'), **incident_evidence_gate(article, context_anchor)}
            for article in search_result['articles']
        ],
        "evidence_gate_audit": [
            {"url": article.get("url"), "stage": "attribution_anchors",
             **attribution_evidence_gate(article, claim, anchors_only=True)}
            for article in search_result["articles"] if article.get("status") == "extracted"
        ],
        "is_quote_derived": bool(claim.get("is_quote_derived")),
        "quote_paraphrase": quote_paraphrase,
        "scoring_claim": scoring_claim,
        "search_query": retrieval_query,
        "event_search_query": (
            shared_evidence_pool.get("query")
            if shared_evidence_pool and shared_evidence_pool.get("used")
            else None
        ),
        "retrieval_strategy": retrieval_strategy,
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

    if search_status["status"] == "ok" and not review_error:
        timed_stage(
            timings,
            f"{stage_prefix}cache_save",
            lambda: save_cached_verdict(claim_hash, normalized_claim, claim_result),
        )

    event('claim.final', result=claim_result)
    return claim_result

def raise_if_every_review_failed(claim_results):
    """Keeps the explicit retryable 503 when no claim received a verdict."""
    failed_reviews = [result["review_error"] for result in claim_results if result.get("review_error")]
    if failed_reviews and len(failed_reviews) == len(claim_results):
        raise ComponentReviewError(failed_reviews[0]["reason_code"], failed_reviews[0]["failed_stage"])


@traced('request.assemble', dependency=False)
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

def _image_input_error(status, message, http_status=400):
    return {
        "status": status,
        "message": message,
        "http_status": http_status,
    }

@traced('image.download', dependency=True)
def _get_image_bytes_from_url(image_url):
    image_url = str(image_url or "").strip()
    parsed = urlparse(image_url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return _image_input_error(
            "invalid_image_url",
            "Image URL must be an http or https URL.",
            400,
        )

    headers = {
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/bmp,image/tiff,image/*;q=0.8,*/*;q=0.1",
        "User-Agent": "IRIS/1.0 image verification",
    }
    response = None

    try:
        response = requests.get(
            image_url,
            headers=headers,
            stream=True,
            timeout=REMOTE_IMAGE_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        return _image_input_error(
            "remote_image_timeout",
            "IRIS timed out while fetching the image URL.",
            504,
        )
    except requests.RequestException as error:
        return _image_input_error(
            "remote_image_failed",
            f"IRIS could not fetch the image URL: {error}",
            502,
        )

    try:
        if response.status_code >= 400:
            return _image_input_error(
                "remote_image_failed",
                f"Image URL returned HTTP {response.status_code}.",
                502,
            )

        raw_content_type = response.headers.get("content-type", "")
        content_type = raw_content_type.split(";", 1)[0].strip().lower()
        if (
            content_type
            and not content_type.startswith("image/")
            and content_type != "application/octet-stream"
        ):
            return _image_input_error(
                "unsupported_image_type",
                "Image URL did not return an image file.",
                400,
            )

        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_IMAGE_BYTES:
                    return _image_input_error(
                        "image_too_large",
                        f"Image is larger than the {MAX_IMAGE_BYTES} byte OCR limit.",
                        413,
                    )
            except ValueError:
                pass

        chunks = []
        total_size = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue

            total_size += len(chunk)
            if total_size > MAX_IMAGE_BYTES:
                return _image_input_error(
                    "image_too_large",
                    f"Image is larger than the {MAX_IMAGE_BYTES} byte OCR limit.",
                    413,
                )

            chunks.append(chunk)

        image_bytes = b"".join(chunks)
        validation = validate_image_bytes(image_bytes)
        if validation["status"] != "ok":
            return validation

        validation["image_bytes"] = image_bytes
        validation["source_url"] = image_url
        return validation
    finally:
        close = getattr(response, "close", None)
        if close:
            close()

@traced('image.acquire_decode', dependency=False)
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

    for key in ["image_url", "url", "src_url"]:
        if data.get(key):
            return _get_image_bytes_from_url(data[key])

    return {
        "status": "missing_image",
        "message": "Provide an image file, an image URL, or a base64 image field.",
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

@traced('text.process', dependency=False)
def verify_text_payload(text, debug_enabled=False, timings=None, from_image=False):
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

    event('text.route', eligible=content_profile['eligible_for_verification'], route=content_profile['recommended_route'], ignored_segments=content_profile.get('ignored_segments'))
    if content_profile["eligible_for_verification"] and scriptural_narrative(
            " ".join(part for part in [text, translated] if part)):
        # Scripture is not reported as news, and "Verified" on it reads as IRIS endorsing a
        # religious account as fact (held-out post H22).
        event('stage.skipped', stages=['claims.extract','event.retrieve','claim.process'],
              reason='scriptural_narrative')
        response = build_out_of_scope_response(
            text, translated, language, debug_enabled, opinion_result, political_result,
            content_profile, {'in_scope': True, 'reason': 'scriptural_narrative'},
            verdict=SCRIPTURE_VERDICT, message=scripture_message(),
            route="stop_scriptural_narrative")
        return complete_response(response)

    scope = timed_stage(timings, "text.coverage_scope", lambda: philippine_scope(text, translated))
    if content_profile["eligible_for_verification"] and not scope["in_scope"]:
        # Eleven Philippine publishers have nothing to say about a galaxy 24 million light-years
        # away (saved case B16), and three Not Found verdicts read as a failed check.
        event('stage.skipped', stages=['claims.extract','event.retrieve','claim.process'],
              reason='outside_philippine_coverage', subject=scope.get('subject'))
        response = build_out_of_scope_response(text, translated, language, debug_enabled,
                                               opinion_result, political_result, content_profile, scope)
        return complete_response(response)

    if not content_profile["eligible_for_verification"]:
        event('stage.skipped', stages=['claims.extract','event.retrieve','claim.process'], reason=content_profile['recommended_route'])
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

    general_only = only_general_statements(claim_extraction["claims"], content_profile)
    if general_only:
        # Saved case B07: five statements about what one vote can influence, searched across
        # eleven publishers, answered Not Found five times. No source can confirm a sentence
        # that names nobody, nothing and no date.
        claim_extraction = {**claim_extraction, "claims": [], "status": "no_checkable_claims_general"}

    if not claim_extraction["claims"]:
        flags = ["politically_sensitive"] if politically_sensitive else []
        verdict = "Opinion Detected" if opinion_result["is_opinion"] else "No Checkable Claims"
        message = (
            "This appears to be an opinion, so IRIS did not perform fact-checking."
            if verdict == "Opinion Detected"
            else "IRIS did not find factual claims that can be checked against sources."
        )
        if general_only:
            message = (
                "IRIS did not check this post: its statements are general and name no person, "
                "institution, number or date that a news source could confirm."
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

    from pipeline.attribution_integrity import ground_attribution
    claim_extraction["claims"] = [
        ground_attribution(claim, text + "\n" + (translated or ""))
        for claim in claim_extraction["claims"]
    ]
    for claim in claim_extraction['claims']:
        # Context identifies the incident for pronouns; it is never supporting evidence.
        claim['evidence_context'] = normalized_verification_text or verification_text
        claim['from_image'] = from_image
        if language in ["tagalog", "taglish"]:
            claim['original_language_query'] = original_language_query(
                claim.get('claim_text') or claim.get('normalized_claim') or '', text, translated)
    trace = CURRENT.get()
    if trace and trace.stop_claim is not None and trace.stop_claim not in {str(c['claim_id']) for c in claim_extraction['claims']}:
        from iris_trace.core import TargetNotReached
        raise TargetNotReached(trace.stop_after, 'Claim ID was not extracted; downstream retrieval was not started.')
    # Step 5: Mark quote-derived claims and build one reusable event pool.
    claim_extraction["claims"] = timed_stage(
        timings,
        "text.mark_quote_derived_claims",
        lambda: mark_quote_derived_claims(
            claim_extraction["claims"],
            content_profile,
        ),
    )
    shared_evidence_pool = timed_stage(
        timings,
        "text.shared_event_evidence_pool",
        lambda: build_shared_event_evidence_pool(
            text,
            translated,
            claim_extraction["claims"],
            content_profile,
        ),
    )

    # Step 6: Verify each extracted factual claim independently.
    claim_results = timed_stage(
        timings,
        "text.verify_claims_total",
        lambda: [
            verify_claim(claim, language, timings, shared_evidence_pool)
            for claim in claim_extraction["claims"]
        ],
    )
    raise_if_every_review_failed(claim_results)
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
        "searched_sources": "VERA Files and Rappler + 9 approved Philippine news sources",
    }, debug_enabled, opinion_result, political_result, content_profile)
    response = add_single_claim_compatibility_fields(response, claim_results)

    if debug_enabled:
        response["debug"]["claim_extraction"] = claim_extraction
        response["debug"]["shared_evidence_pool"] = summarize_shared_evidence_pool(
            shared_evidence_pool
        )

    return complete_response(response)

from pipeline.component_evidence import ComponentReviewError
from pipeline.quotation_context import QuotationExtractionError


@app.errorhandler(QuotationExtractionError)
def quotation_extraction_error(error):
    return jsonify({'status': 'processing_error', 'error': 'quotation_extraction_failed',
                    'message': 'IRIS could not safely extract the reported quotations. Please retry; no verdict was issued.',
                    'retryable': True, 'verdict': None, 'evidence_sources': [],
                    'reason_code': str(error), 'failed_stage': 'claim_extraction'}), 503


@app.errorhandler(ComponentReviewError)
def component_review_error(error):
    app.logger.error('Evidence review failed: stage=%s reason=%s', error.stage, error.reason_code)
    return jsonify({"status": "processing_error", "error": "component_review_failed",
                    "message": str(error), "retryable": True, "verdict": None,
                    "evidence_sources": [], "reason_code": error.reason_code,
                    "failed_stage": error.stage}), 503


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
        lambda: verify_text_payload(ocr_result["text"], debug_enabled, timings, from_image=True),
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
