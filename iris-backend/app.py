
from iris_trace.core import traced, event, CURRENT, submit_context
from concurrent.futures import ThreadPoolExecutor
import hmac
import logging
import os
import re
import time
import uuid
from urllib.parse import urlparse

import requests
from flask import Flask, request, jsonify
from pipeline.cache import get_cached_verdict, hash_claim, save_cached_verdict
from pipeline.attribution_integrity import (attribution_phrase_match, date_phrase_match,
                                            is_calendar_date, speaker_phrase_match, speaker_query)
from pipeline.evidence_urls import article_url_rejection, is_opinion_url
from pipeline.checkable_claims import only_general_statements
from pipeline.claim_extractor import extract_claims
from pipeline.component_evidence import REFUTED_VERDICT
from pipeline.content_profiler import profile_content
from pipeline.coverage_scope import (OUT_OF_SCOPE_VERDICT, SCRIPTURE_VERDICT, out_of_scope_message,
                                     philippine_scope, scriptural_narrative, scripture_message)
from pipeline.event_retrieval import mark_quote_derived_claims
from pipeline.language_detector import detect_language
from pipeline.ocr import (
    MAX_IMAGE_BYTES,
    decode_base64_image,
    extract_text_from_image,
    validate_image_bytes,
)
from pipeline.opinion_filter import is_opinion
from pipeline.political_checker import flag_political, flag_claim_political
from pipeline.quotation_context import restore_original_quotations
from pipeline.safe_fetch import UnsafeImageURL, get_public_url
from pipeline.search import search_and_extract
from pipeline.search_queries import anchored_query, original_language_query
from pipeline.translator import translate_to_english

app = Flask(__name__)
app.json.sort_keys = False
from iris_trace.web import init_app as init_trace
init_trace(app)
logging.basicConfig(level=logging.INFO)
RESULT_CACHE_VERSION = "week8-own-search-v40"
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


def build_claim_cache_basis(normalized_claim, claim, scoring_claim=None, shared_evidence_pool=None):
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


@traced('claim.retrieve', dependency=False)
def build_claim_search_result(claim, language, retrieval_query, normalized_claim, shared_evidence_pool=None):
    """
    Searches for this one claim, in its own words.

    Claims taken from quotations used to skip this and read only one search built for the whole
    post out of its capitalised words ("... READ MORE Sarablamesadmin See Para administration").
    The claim's own query, its Filipino sentence and the fact-check lookup never ran, and the
    article that verifies the quotation was never found (diagnosed 22 September; held-out H15 and
    H16 lost their references the same way). Every claim now searches on its own, and what the
    claims of a post find is shared between them afterwards.
    """
    attribution = claim.get("attribution") or {}
    translated_query = None
    if claim.get("quote_translation"):
        # The claim keeps a quotation in the language it was said in; its English rendering
        # searches for reporting that printed the quotation in English. It takes the place of the
        # original-language pass, whose words the claim itself now carries.
        translated_query = (speaker_query(attribution.get("speaker"), claim["quote_translation"])
                            if claim.get("claim_type") == ATTRIBUTED_CLAIM_TYPE
                            else claim["quote_translation"])
    search_result = search_and_extract(
        primary_query=retrieval_query,
        backup_query=(
            normalized_claim
            if retrieval_query.strip().lower() != normalized_claim.strip().lower()
            else claim["claim_text"] if language in ["tagalog", "taglish"] else None
        ),
        original_language_query=(
            None if translated_query
            else claim.get("original_language_query") if language in ["tagalog", "taglish"] else None
        ),
        # A picture's claim can lose the very name that finds its fact-check: held-out post
        # H18 kept "EDU MANZANO" in the reading and lost it from the claim, while the fact-check
        # is filed under his name. The sitemap lookup ranks by rare words, so giving it the
        # post's own words costs nothing and finds what the claim cannot.
        fact_check_text=" ".join(part for part in [
            claim.get("claim_text") or normalized_claim,
            claim.get("evidence_context", "") if claim.get("from_image") else ""] if part),
        translated_query=translated_query,
    )
    return search_result, "claim_search_only"


def plan_claim(claim, timings=None):
    """The claim's search query, incident anchor and cache key, which every later stage reads."""
    from pipeline.claim_context import incident_anchor, contextual_search_query
    normalized_claim = claim["normalized_claim"]
    context_anchor = incident_anchor(normalized_claim, claim.get('evidence_context', ''))
    retrieval_query = contextual_search_query(claim.get("search_query") or normalized_claim, context_anchor)
    # Keep the claim's dates, numbers and short titles that the generated query dropped.
    retrieval_query = anchored_query(retrieval_query, claim.get("claim_text") or normalized_claim)
    stage_prefix = f"claim_{claim.get('claim_id', 'unknown')}."
    cache_basis = build_claim_cache_basis(normalized_claim, claim)
    claim_hash = timed_stage(timings, f"{stage_prefix}hash_claim", lambda: hash_claim(cache_basis))
    return {"normalized_claim": normalized_claim, "context_anchor": context_anchor,
            "retrieval_query": retrieval_query, "stage_prefix": stage_prefix, "claim_hash": claim_hash}


def cached_claim_result(plan, timings=None):
    cached = timed_stage(timings, f"{plan['stage_prefix']}cache_lookup",
                         lambda: get_cached_verdict(plan["claim_hash"]))
    if cached and cached.get("cache_version") == RESULT_CACHE_VERSION:
        return cached
    return None


@traced('claim.gather', dependency=False)
def gather_claim_evidence(claim, language, plan, timings=None):
    """
    The part of a claim's check that does not depend on the post's other claims.

    After the claim's own search, the reviewer splits the claim into components, which needs only
    the claim and the post, while the post's other claims are still searching. It is only asked
    for when the search returned an article the review could read, so a claim with nothing to
    review costs no model call. Nothing here decides a verdict.

    Passages are not embedded here. Embedding every readable article before the gates and the
    reading budget were applied doubled the embedding a post with many claims waited for (in the
    34-case check A08 needed 29 seconds of it, against 5 for what its reviews used), because
    claims embed one at a time. The review embeds the passages of the articles it reads.
    """
    from pipeline.component_evidence import prepare_component_review
    stage_prefix = plan["stage_prefix"]
    search_result, strategy = timed_stage(
        timings, f"{stage_prefix}search_and_extract",
        lambda: build_claim_search_result(claim, language, plan["retrieval_query"],
                                          plan["normalized_claim"]))
    search_status = timed_stage(timings, f"{stage_prefix}search_status",
                                lambda: get_search_status(search_result))
    readable = [article for article in search_result.get("articles") or []
                if article.get("status") == "extracted" and article.get("text")
                and compact_evidence_source(article)]
    prepared = None
    if search_status["status"] == "ok" and readable:
        prepared = timed_stage(
            timings, f"{stage_prefix}component_prepare",
            lambda: prepare_component_review(claim.get("claim_text") or plan["normalized_claim"],
                                             claim.get("evidence_context", "")))
    return {"plan": plan, "search_result": search_result, "retrieval_strategy": strategy,
            "search_status": search_status, "prepared": prepared}


# At most this many articles found by a post's other claims join one claim's evidence.
MAX_SHARED_ARTICLES = max(0, int(os.getenv("IRIS_MAX_SHARED_ARTICLES", "12")))
SHARED_ARTICLE_MIN_TERMS = 2


def post_article_pool(gathered):
    """Every readable article the claims of a post found, once each, with the claims that found it."""
    pool, by_url = [], {}
    for claim_id, found in gathered.items():
        for article in (found.get("search_result") or {}).get("articles") or []:
            key = normalize_evidence_url(article.get("url"))
            if not key or article.get("status") != "extracted" or not article.get("text"):
                continue
            if key in by_url:
                by_url[key]["found_by"].append(claim_id)
                continue
            by_url[key] = {"key": key, "article": article, "found_by": [claim_id]}
            pool.append(by_url[key])
    return pool


def shared_candidates(claim, own_articles, pool, limit=MAX_SHARED_ARTICLES):
    """
    Articles the post's other claims found that this claim's own search did not.

    The claims of a post are about the same events, and one claim's search can find what another
    needs: held-out post H17 verified its first claim on an ABS-CBN story that also printed the
    quotation of its second claim, which the second claim's own search never returned. The
    articles sharing most of the claim's words come first. They pass every gate and review a
    claim's own articles pass; sharing them is not evidence by itself.
    """
    own = {normalize_evidence_url(article.get("url")) for article in own_articles}
    # A quotation kept in Filipino shares few words with English reporting of it, so its English
    # rendering and the speaker's name count too: in saved case A02 the article carrying the
    # exchange ranked outside the twelve offered on the Filipino words alone, and first with them.
    attribution = claim.get("attribution") or {}
    wanted = set(evidence_terms(" ".join(str(value or "") for value in (
        claim.get("claim_text"), claim.get("normalized_claim"), claim.get("quote_translation"),
        attribution.get("speaker")))))
    ranked = []
    for order, entry in enumerate(pool):
        if entry["key"] in own:
            continue
        overlap = len(wanted & set(evidence_terms(evidence_text(entry["article"]))))
        if overlap >= SHARED_ARTICLE_MIN_TERMS:
            ranked.append((-overlap, order, entry["article"]))
    ranked.sort(key=lambda item: item[:2])
    return [{**article, "evidence_pool": "post_shared"} for _, _, article in ranked[:limit]]


@traced('claim.process', dependency=False)
def verify_claim(claim, language, timings=None, gathered=None, shared_articles=None):
    """Checks one claim against its own search, the post's shared articles and the component review."""
    from pipeline.claim_context import incident_evidence_gate
    plan = (gathered or {}).get("plan") or plan_claim(claim, timings)
    cached_result = gathered.get("cached") if gathered else cached_claim_result(plan, timings)
    if cached_result:
        event('stage.skipped', stages=['claim.gather', 'claim.retrieve', 'claim.component_review'],
              reason='Matching cache entry reused')
        event('cache.hit', claim_id=claim['claim_id'], cache_version=cached_result.get('cache_version'),
              downstream='retrieval and review bypassed')
        cached_result["claim_id"] = claim["claim_id"]
        cached_result["claim_text"] = claim["claim_text"]
        cached_result["is_quote_derived"] = bool(claim.get("is_quote_derived"))
        cached_result["cache_hit"] = True
        return cached_result
    if not gathered or "search_result" not in gathered:
        gathered = gather_claim_evidence(claim, language, plan, timings)

    normalized_claim = plan["normalized_claim"]
    stage_prefix = plan["stage_prefix"]
    context_anchor = plan["context_anchor"]
    claim_flags = timed_stage(
        timings,
        f"{stage_prefix}political_flags",
        lambda: get_claim_flags(normalized_claim, claim),
    )
    search_result = gathered["search_result"]
    search_status = gathered["search_status"]
    own_articles = list(search_result.get("articles") or [])
    shared = shared_candidates(claim, own_articles, shared_articles) if shared_articles else []
    candidates = own_articles + shared
    # A claim whose own search came back empty can still be checked on what its siblings found;
    # a search that failed or is not configured stays a technical result.
    search_ok = search_status["status"] == "ok" or (search_status["status"] == "no_results" and bool(shared))
    final_verdict = search_status.get("verdict")
    final_message = search_status.get("message")
    evidence_sources = []
    eligible = []

    component_review = None
    review_error = None
    if search_ok:
        from pipeline.component_evidence import (
            ComponentReviewError,
            require_completed_review,
            review_components,
        )
        eligible = [article for article in candidates
                    if compact_evidence_source(article)
                    and article.get("text")
                    and not opinion_evidence_blocked(article, claim)
                    and attribution_evidence_gate(article, claim, anchors_only=True)["matches"]
                    and incident_evidence_gate(article, context_anchor)["matches"]]
        opinion_excluded = [article.get("url") for article in candidates
                            if article.get("text") and opinion_evidence_blocked(article, claim)]
        if opinion_excluded:
            event('evidence.opinion_excluded', urls=opinion_excluded, claim_type=claim.get("claim_type"))
        event('evidence.incident_gate', anchor=context_anchor, articles=[
            {'url': article.get('url'), **incident_evidence_gate(article, context_anchor)}
            for article in candidates])
        component_review = timed_stage(
            timings, f"{stage_prefix}component_evidence_review",
            lambda: review_components(claim.get('claim_text') or normalized_claim, eligible,
                                      source_context=claim.get('evidence_context', ''),
                                      prepared=gathered.get("prepared"),
                                      claim_translation=claim.get("quote_translation")),
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
            event('verdict.review_failed', before=None, after=REVIEW_FAILED_VERDICT, **review_error)
            final_verdict = REVIEW_FAILED_VERDICT
            final_message = REVIEW_FAILED_MESSAGE
            evidence_sources = []
        else:
            event('verdict.component_review', before=None, after=component_review.get('verdict'),
                  details=component_review)
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
    shared_used = [article.get("url") for article in eligible if article.get("evidence_pool") == "post_shared"]

    claim_result = {
        "claim_id": claim["claim_id"],
        "claim_text": claim["claim_text"],
        "normalized_claim": normalized_claim,
        "claim_type": claim.get("claim_type", "factual_claim"),
        "verification_focus": claim.get("verification_focus", claim.get("claim_type", "factual_claim")),
        "attribution": claim.get("attribution"),
        "attribution_integrity": claim.get("attribution_integrity"),
        "quote_translation": claim.get("quote_translation"),
        "restored_quotations": claim.get("restored_quotations"),
        "component_review": component_review,
        "review_error": review_error,
        "incident_evidence_audit": [
            {'url': article.get('url'), **incident_evidence_gate(article, context_anchor)}
            for article in candidates
        ],
        "evidence_gate_audit": [
            {"url": article.get("url"), "stage": "attribution_anchors",
             **attribution_evidence_gate(article, claim, anchors_only=True)}
            for article in candidates if article.get("status") == "extracted"
        ],
        "is_quote_derived": bool(claim.get("is_quote_derived")),
        # Kept for clients and reports that read them: the paraphrase and the similarity score
        # it fed no longer run, since the component review decided every verdict without them.
        "quote_paraphrase": {"used_for_scoring": False, "status": "not_run", "method": "not_run",
                             "error": None, "paraphrase": normalized_claim},
        "scoring_claim": normalized_claim,
        "search_query": plan["retrieval_query"],
        "event_search_query": None,
        "retrieval_strategy": ("claim_search_plus_post_pool" if shared_used
                               else gathered.get("retrieval_strategy") or "claim_search_only"),
        "shared_evidence": {"offered": len(shared), "eligible": len(shared_used), "urls": shared_used},
        "risk_tags": claim.get("risk_tags", []),
        "claim_hash": plan["claim_hash"],
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
        "total_search_results": search_result.get("total_search_results", 0),
        "searched_articles": search_result.get("searched_articles", 0),
        "extracted_articles": search_result.get("extracted_articles", 0),
        "source_summary": search_result.get("source_summary", []),
        "sources": evidence_sources,
        "evidence_sources": evidence_sources,
        "evidence_policy": (
            "Only valid http/https links from extracted evidence used for the "
            "verdict are shown. Attributed claims also require speaker/source/"
            "program/date anchors when those anchors are part of the claim."
        ),
        "fallback": {
            "openai": {"used": False, "status": "not_run", "error": None, "result": None},
            "keyword_overlap": None,
        },
    }

    if search_ok and not review_error:
        timed_stage(
            timings,
            f"{stage_prefix}cache_save",
            lambda: save_cached_verdict(plan["claim_hash"], normalized_claim, claim_result),
        )

    event('claim.final', result=claim_result)
    return claim_result

# The claims of a post search at the same time: a search waits on Brave and publishers, and
# claims searched one after another were what made a long post slow. Five at a time keeps the
# process inside the Brave plan's 50 requests a second (search.py paces every request anyway).
SEARCH_CLAIM_WORKERS = max(1, int(os.getenv("IRIS_SEARCH_CLAIM_WORKERS", "5")))
# Reviews wait on the review model, three at a time as before: well inside its token limit, and
# kind to the other people using the same backend.
CLAIM_WORKERS = max(1, int(os.getenv("IRIS_CLAIM_WORKERS", "3")))


def _each(fn, items, workers, prefix):
    """fn(*item) for every item, a few at a time, results in the order of the items."""
    if len(items) < 2 or workers < 2:
        return [fn(*item) for item in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items)), thread_name_prefix=prefix) as executor:
        futures = [submit_context(executor, fn, *item) for item in items]
        return [future.result() for future in futures]


def verify_claims(claims, language, timings):
    """
    Checks every claim of a post: first all of them search, then they are reviewed.

    Searching first lets each claim's review see what the post's other claims found, and puts the
    waiting on Brave and publishers into one stretch at the start instead of once per round of
    reviews. Returns the claim results in extraction order and a summary of the shared pool.
    """
    plans = [plan_claim(claim, timings) for claim in claims]
    cached = [cached_claim_result(plan, timings) for plan in plans]
    pending = [(claim, language, plan, timings) for claim, plan, hit in zip(claims, plans, cached) if not hit]
    found = _each(gather_claim_evidence, pending, SEARCH_CLAIM_WORKERS, "iris-search")
    gathered = {str(item[0].get("claim_id")): evidence for item, evidence in zip(pending, found)}
    pool = post_article_pool(gathered) if len(claims) > 1 else []
    work = [(claim, language, timings,
             {"plan": plan, "cached": hit} if hit else gathered[str(claim.get("claim_id"))],
             pool)
            for claim, plan, hit in zip(claims, plans, cached)]
    results = _each(verify_claim, work, CLAIM_WORKERS, "iris-claim")
    return results, {"articles": len(pool), "claims_searched": len(pending),
                     "found_by_several_claims": sum(1 for entry in pool if len(entry["found_by"]) > 1)}


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
        response = get_public_url(
            image_url,
            headers=headers,
            stream=True,
            timeout=REMOTE_IMAGE_TIMEOUT_SECONDS,
        )
    except UnsafeImageURL as error:
        return _image_input_error(
            "unsafe_image_url",
            str(error),
            400,
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
    # Quotations go back into the words they were said in before anything searches with them.
    claim_extraction["claims"] = [
        ground_attribution(restore_original_quotations(claim, text, translated),
                           text + "\n" + (translated or ""))
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
    # Step 5: Mark quote-derived claims.
    claim_extraction["claims"] = timed_stage(
        timings,
        "text.mark_quote_derived_claims",
        lambda: mark_quote_derived_claims(
            claim_extraction["claims"],
            content_profile,
        ),
    )

    # Step 6: Verify every claim. The claims of a post search together and share what they find.
    claim_results, post_pool = timed_stage(
        timings,
        "text.verify_claims_total",
        lambda: verify_claims(claim_extraction["claims"], language, timings),
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
        response["debug"]["post_evidence_pool"] = post_pool

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


API_TOKEN = os.getenv("IRIS_API_TOKEN", "").strip()

# An 8 MB image arrives base64 encoded, so about 10.7 MB of JSON. Sixteen leaves room for that
# and for the fields around it, and stops one oversized body from taking memory away from the
# other people in a session -- there is one process serving all of them.
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("IRIS_MAX_REQUEST_BYTES", str(16 * 1024 * 1024)))


@app.route('/health')
def health():
    """
    Answers the host's health check without loading a model.

    The check runs every few seconds, so it stays cheap on purpose: it says the process is up
    and serving, not that a verification would succeed.
    """
    return jsonify({"status": "ok", "service": "iris", "pipeline": RESULT_CACHE_VERSION})


@app.before_request
def require_token():
    """
    Asks callers of the verification endpoints for the shared token.

    Every check spends OpenAI and Brave credit, so on a public address the endpoints cannot be
    open to anyone who finds the URL. With IRIS_API_TOKEN unset nothing changes, which keeps
    local development and the tests as they were. TRACE is not covered here because it does
    its own, stricter check in iris_trace/web.py.
    """
    if not API_TOKEN or request.method == "OPTIONS":
        return None

    if not request.path.startswith("/verify"):
        return None

    offered = request.headers.get("X-IRIS-Token", "")
    if not offered:
        offered = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()

    if hmac.compare_digest(str(offered), API_TOKEN):
        return None

    return jsonify({
        "status": "processing_error",
        "error": "unauthorized",
        "message": "This IRIS backend needs an access token. Set it in the IRIS options.",
        "retryable": False,
        "verdict": None,
        "evidence_sources": [],
    }), 401


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
    # Development only. On a host, gunicorn imports `app` from this file instead, so neither
    # the reloader nor the Werkzeug debugger -- which runs whatever a caller sends it -- can
    # ever be reached there. Debug is now something you ask for rather than something you get.
    app.run(
        host=os.getenv("IRIS_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"},
    )
