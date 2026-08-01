"""
Simple Week 4 endpoint check.

Run from the iris-backend folder:
    python tests/test_week4_app.py
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app as iris_app


def _fake_content_profile(
    verification_text,
    normalized_verification_text,
    post_type="fact_only",
    ignored_segments=None,
    contains_opinion=False,
    contains_recommendation=False,
):
    ignored_segments = ignored_segments or []

    return {
        "status": "ok",
        "method": "test_stub",
        "error": None,
        "post_type": post_type,
        "confidence": 0.90,
        "ambiguity_score": 0.0,
        "ambiguity_reasons": [],
        "contains_factual_claims": True,
        "contains_opinion": contains_opinion,
        "contains_recommendation": contains_recommendation,
        "contains_forecast_or_projection": False,
        "contains_satire_or_humor": False,
        "contains_quote": False,
        "eligible_for_verification": True,
        "recommended_route": (
            "verify_factual_claims_only"
            if ignored_segments
            else "proceed_to_verification"
        ),
        "verification_text": verification_text,
        "normalized_verification_text": normalized_verification_text,
        "segments": [],
        "ignored_segments": ignored_segments,
        "user_notification": None,
        "openai_profile": {
            "used": False,
            "status": "not_run",
            "error": None,
            "result": None,
        },
    }


def _fake_search_result():
    return {
        "total_search_results": 1,
        "searched_articles": 1,
        "extracted_articles": 1,
        "articles": [
            {
                "source": "GMA News",
                "title": "DOH reports dengue cases",
                "url": "https://example.com/dengue",
                "description": "DOH reported new dengue cases.",
                "status": "extracted",
                "word_count": 80,
                "error": None,
                "text": "The Department of Health reported new dengue cases.",
            }
        ],
        "source_summary": [
            {
                "source": "GMA News",
                "results_found": 1,
                "articles_checked": 1,
                "articles_extracted": 1,
            }
        ],
        "search": {
            "searches": [
                {
                    "source_reports": [
                        {
                            "source": "GMA News",
                            "status": "ok",
                        }
                    ]
                }
            ]
        },
    }


def _fake_verdict(claim, articles):
    return {
        "verdict": "Partially Verified",
        "reason": f"Fake similarity result for: {claim}",
        "corroboration_count": 1,
        "primary_evidence": {
            "source": "GMA News",
            "title": "DOH reports dengue cases",
            "url": "https://example.com/dengue",
            "similarity_score": 0.8,
            "status": "extracted",
            "word_count": 80,
        },
        "supporting_sources": [],
        "similarity_thresholds": {
            "verified": 0.85,
            "partial": 0.5,
        },
    }


def run_checks() -> None:
    originals = {
        "detect_language": iris_app.detect_language,
        "translate_to_english": iris_app.translate_to_english,
        "profile_content": iris_app.profile_content,
        "is_opinion": iris_app.is_opinion,
        "extract_claims": iris_app.extract_claims,
        "search_and_extract": iris_app.search_and_extract,
        "generate_verdict": iris_app.generate_verdict,
        "refine_with_openai_rag": iris_app.refine_with_openai_rag,
        "get_cached_verdict": iris_app.get_cached_verdict,
        "save_cached_verdict": iris_app.save_cached_verdict,
    }

    try:
        iris_app.detect_language = lambda text: "taglish"
        iris_app.translate_to_english = lambda text, language: (
            "The Department of Health reported new dengue cases. "
            "The mayor announced flood aid."
        )
        iris_app.profile_content = lambda text, translated: _fake_content_profile(
            text,
            translated,
        )
        iris_app.is_opinion = lambda text: {
            "is_opinion": False,
            "matched_phrases": [],
            "matched_words": [],
        }
        iris_app.extract_claims = lambda text, translated: {
            "status": "missing_api_key",
            "method": "local_sentence_split",
            "error": "Test fallback.",
            "post_type": "mixed_content",
            "contains_opinion": False,
            "contains_recommendation": False,
            "ignored_segments": [],
            "claims": [
                {
                    "claim_id": 1,
                    "claim_text": "The Department of Health reported new dengue cases.",
                    "normalized_claim": "The Department of Health reported new dengue cases.",
                },
                {
                    "claim_id": 2,
                    "claim_text": "The mayor announced flood aid.",
                    "normalized_claim": "The mayor announced flood aid.",
                },
            ],
        }
        iris_app.search_and_extract = lambda primary_query, backup_query=None: _fake_search_result()
        iris_app.generate_verdict = _fake_verdict
        iris_app.refine_with_openai_rag = lambda claim, articles, verdict_result: {
            "used": False,
            "status": "not_needed",
            "error": None,
            "result": None,
        }
        iris_app.get_cached_verdict = lambda claim_hash: None
        iris_app.save_cached_verdict = lambda claim_hash, claim_text, result: None

        client = iris_app.app.test_client()
        response = client.post(
            "/verify",
            json={
                "text": "DOH may bagong dengue cases. Nag-announce ang mayor ng flood aid."
            },
        )
        payload = response.get_json()

        assert response.status_code == 200
        assert payload["verdict"] == "Multiple Claims Checked"
        assert payload["claim_count"] == 2
        assert len(payload["claims"]) == 2
        assert payload["claims"][0]["politically_sensitive"] is False
        assert payload["claims"][1]["politically_sensitive"] is True

        iris_app.is_opinion = lambda text: {
            "is_opinion": True,
            "matched_phrases": [],
            "matched_words": ["should"],
        }
        iris_app.profile_content = lambda text, translated: _fake_content_profile(
            "Fugitive Bato Dela Rosa has a whopping 118 licensed firearms.",
            "Fugitive Bato Dela Rosa has a whopping 118 licensed firearms.",
            post_type="mixed_content",
            ignored_segments=[
                {
                    "segment_id": "s2",
                    "text": "Delikado!",
                    "segment_type": "opinion",
                    "reason_codes": ["emotional_or_persuasive_language"],
                    "recommended_route": "stop_opinion_detected",
                    "user_notification": "IRIS skipped this opinion segment.",
                },
                {
                    "segment_id": "s3",
                    "text": "The PNP should revoke all of his licenses.",
                    "segment_type": "recommendation",
                    "reason_codes": ["call_to_action"],
                    "recommended_route": "stop_opinion_detected",
                    "user_notification": "IRIS skipped this recommendation.",
                },
            ],
            contains_opinion=True,
            contains_recommendation=True,
        )
        iris_app.extract_claims = lambda text, translated: {
            "status": "missing_api_key",
            "method": "local_sentence_split",
            "error": "Test fallback.",
            "post_type": "mixed_content",
            "contains_opinion": True,
            "contains_recommendation": True,
            "ignored_segments": [
                {
                    "text": "Delikado!",
                    "segment_type": "opinion",
                },
                {
                    "text": "The PNP should revoke all of his licenses.",
                    "segment_type": "recommendation",
                },
            ],
            "claims": [
                {
                    "claim_id": 1,
                    "claim_text": "Bato Dela Rosa has 118 licensed firearms.",
                    "normalized_claim": "Bato Dela Rosa has 118 licensed firearms.",
                    "claim_type": "factual_claim",
                    "risk_tags": ["weapons_claim", "high_risk_claim"],
                },
                {
                    "claim_id": 2,
                    "claim_text": "Bato Dela Rosa is a fugitive from justice.",
                    "normalized_claim": "Bato Dela Rosa is a fugitive from justice.",
                    "claim_type": "factual_claim",
                    "risk_tags": ["criminal_allegation", "high_risk_claim"],
                },
            ],
        }

        messy_response = client.post(
            "/verify",
            json={
                "text": (
                    "Fugitive Bato Dela Rosa has a whopping 118 licensed firearms. "
                    "Delikado! The PNP should revoke all of his licenses."
                )
            },
        )
        messy_payload = messy_response.get_json()

        assert messy_response.status_code == 200
        assert messy_payload["verdict"] == "Multiple Claims Checked"
        assert messy_payload["post_type"] == "mixed_content"
        assert messy_payload["contains_opinion"] is True
        assert messy_payload["contains_recommendation"] is True
        assert messy_payload["claim_count"] == 2
        assert messy_payload["claims"][0]["claim_type"] == "factual_claim"
        assert "weapons_claim" in messy_payload["claims"][0]["risk_tags"]
    finally:
        for name, value in originals.items():
            setattr(iris_app, name, value)

    print("All Week 4 endpoint checks passed.")


if __name__ == "__main__":
    run_checks()
