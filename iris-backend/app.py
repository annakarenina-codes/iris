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
RESULT_CACHE_VERSION = "week5-content-profiler-v1"

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

def apply_low_confidence_fallback(claim_text, articles, verdict_result):
    """Runs OpenAI RAG first, then local keyword overlap if OpenAI cannot run."""
    openai_result = refine_with_openai_rag(claim_text, articles, verdict_result)
    keyword_result = None
    final_verdict = verdict_result["verdict"]
    final_message = verdict_result["reason"]

    if openai_result["status"] == "ok" and openai_result["result"]:
        final_verdict = openai_result["result"]["verdict"]
        final_message = openai_result["result"]["reason"]
    elif openai_result["status"] not in ["not_needed", "no_evidence"]:
        keyword_result = keyword_overlap_verdict(claim_text, articles)
        final_verdict = keyword_result["verdict"]
        final_message = keyword_result["reason"]

    return {
        "verdict": final_verdict,
        "message": final_message,
        "openai_fallback": openai_result,
        "keyword_fallback": keyword_result,
    }

def verify_claim(claim, language):
    """Runs search, scoring, fallback, and caching for one extracted claim."""
    normalized_claim = claim["normalized_claim"]
    claim_hash = hash_claim(normalized_claim)
    cached_result = get_cached_verdict(claim_hash)

    if cached_result and cached_result.get("cache_version") == RESULT_CACHE_VERSION:
        cached_result["claim_id"] = claim["claim_id"]
        cached_result["claim_text"] = claim["claim_text"]
        cached_result["cache_hit"] = True
        return cached_result

    claim_flags = get_claim_flags(normalized_claim)
    search_result = search_and_extract(
        primary_query=normalized_claim,
        backup_query=claim["claim_text"] if language in ["tagalog", "taglish"] else None
    )
    search_status = get_search_status(search_result)
    verdict_result = generate_verdict(normalized_claim, search_result["articles"])

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
        fallback_result = apply_low_confidence_fallback(
            normalized_claim,
            search_result["articles"],
            verdict_result,
        )
        final_verdict = fallback_result["verdict"]
        final_message = fallback_result["message"]

    claim_result = {
        "claim_id": claim["claim_id"],
        "claim_text": claim["claim_text"],
        "normalized_claim": normalized_claim,
        "claim_type": claim.get("claim_type", "factual_claim"),
        "risk_tags": claim.get("risk_tags", []),
        "claim_hash": claim_hash,
        "cache_version": RESULT_CACHE_VERSION,
        "verdict": final_verdict,
        "message": final_message,
        "politically_sensitive": claim_flags["politically_sensitive"],
        "flags": claim_flags["flags"],
        "cache_hit": False,
        "corroboration_count": verdict_result["corroboration_count"],
        "primary_evidence": verdict_result["primary_evidence"],
        "supporting_sources": verdict_result["supporting_sources"],
        "search_status": search_status["status"],
        "total_search_results": search_result["total_search_results"],
        "searched_articles": search_result["searched_articles"],
        "extracted_articles": search_result["extracted_articles"],
        "source_summary": search_result["source_summary"],
        "sources": summarize_sources(
            search_result["source_summary"],
            search_result["articles"]
        ),
        "fallback": {
            "openai": fallback_result["openai_fallback"],
            "keyword_overlap": fallback_result["keyword_fallback"],
        },
    }

    if search_status["status"] == "ok":
        save_cached_verdict(claim_hash, normalized_claim, claim_result)

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

def verify_text_payload(text, debug_enabled=False):
    # Step 1: Detect language
    language = detect_language(text)

    # Step 2: Translate if needed
    translated = translate_to_english(text, language)

    # Step 3: Profile content before claim extraction and retrieval.
    content_profile = profile_content(text, translated)
    opinion_result = is_opinion(text)
    political_result = flag_political(text)
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
        return response

    # Step 4: Extract claims only from profiler-approved factual text.
    verification_text = content_profile["verification_text"]
    normalized_verification_text = content_profile["normalized_verification_text"]
    claim_extraction = extract_claims(verification_text, normalized_verification_text)

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

        return response

    # Step 5: Verify each extracted factual claim independently.
    claim_results = [
        verify_claim(claim, language)
        for claim in claim_extraction["claims"]
    ]
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
        "searched_sources": "VERA Files + 6 approved Philippine news sources",
    }, debug_enabled, opinion_result, political_result, content_profile)
    response = add_single_claim_compatibility_fields(response, claim_results)

    if debug_enabled:
        response["debug"]["claim_extraction"] = claim_extraction

    return response

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
    data = request.get_json(silent=True) if request.is_json else {}
    data = data or {}
    debug_enabled = _truthy(data.get("debug")) or _truthy(request.form.get("debug"))
    image_result = _get_image_bytes_from_request(data)

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
        return jsonify(response), int(image_result.get("http_status", 400))

    ocr_result = extract_text_from_image(image_result["image_bytes"])

    if ocr_result["status"] != "ok" or not ocr_result["text"].strip():
        response = build_ocr_stop_response(ocr_result, debug_enabled)
        return jsonify(response), _ocr_error_http_status(ocr_result)

    response = verify_text_payload(ocr_result["text"], debug_enabled)
    response = add_ocr_response_fields(response, ocr_result, debug_enabled)
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
