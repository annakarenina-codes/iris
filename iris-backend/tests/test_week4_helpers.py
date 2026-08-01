"""
Simple Week 4 helper checks.

Run from the iris-backend folder:
    python tests/test_week4_helpers.py
"""

from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.cache import get_cached_verdict, hash_claim, save_cached_verdict
from pipeline.claim_extractor import _fallback_extract_claims, _fallback_ignored_segments
from pipeline.content_profiler import profile_content
from pipeline.keyword_fallback import keyword_overlap_verdict
from pipeline.openai_fallback import _parse_response
from pipeline.political_checker import flag_political


def run_checks() -> None:
    opinion_profile = profile_content(
        "Sa tingin ko, masama ang bagong policy.",
        use_ai=False,
    )
    assert opinion_profile["eligible_for_verification"] is False
    assert opinion_profile["recommended_route"] == "stop_opinion_detected"
    assert opinion_profile["post_type"] == "opinion_only"

    mixed_profile = profile_content(
        "The Department of Health reported 1,000 dengue cases. "
        "This administration is useless.",
        use_ai=False,
    )
    assert mixed_profile["eligible_for_verification"] is True
    assert mixed_profile["recommended_route"] == "verify_factual_claims_only"
    assert mixed_profile["post_type"] == "mixed_content"
    assert mixed_profile["contains_opinion"] is True
    assert "Department of Health reported" in mixed_profile["verification_text"]
    assert any(
        segment["segment_type"] == "opinion"
        for segment in mixed_profile["ignored_segments"]
    )

    forecast_profile = profile_content(
        "The economy will collapse next year.",
        use_ai=False,
    )
    assert forecast_profile["eligible_for_verification"] is False
    assert forecast_profile["recommended_route"] == "stop_forecast_projection"
    assert forecast_profile["contains_forecast_or_projection"] is True

    claims = _fallback_extract_claims(
        "DOH reported new dengue cases. The mayor announced flood aid."
    )
    assert len(claims) == 2
    assert claims[0]["claim_id"] == 1
    assert "dengue" in claims[0]["normalized_claim"].lower()

    messy_post = (
        "Fugitive Bato Dela Rosa has a whopping 118 licensed firearms. "
        "Some pistols. Some shotguns. And a lot of rifles. Delikado! "
        "As a fugitive from justice, the PNP should REVOKE all of his licenses."
    )
    messy_claims = _fallback_extract_claims(messy_post)
    messy_ignored = _fallback_ignored_segments(messy_post)

    assert len(messy_claims) == 2
    assert messy_claims[0]["normalized_claim"] == "Bato Dela Rosa has a whopping 118 licensed firearms."
    assert "weapons_claim" in messy_claims[0]["risk_tags"]
    assert "criminal_allegation" in messy_claims[1]["risk_tags"]
    assert any(segment["segment_type"] == "opinion" for segment in messy_ignored)
    assert any(segment["segment_type"] == "recommendation" for segment in messy_ignored)

    non_factual = _fallback_extract_claims(
        "Mulat na mga Pilipino sa fake news ng kadiliman. We support and protect BBM."
    )
    assert non_factual == []

    assert flag_political("BBM has control of the Senate.")["politically_sensitive"]
    assert flag_political("Senator Robin Padilla attended the wake.")["politically_sensitive"]

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        cache_path = Path(temp_dir) / "iris_test_cache.sqlite3"
        claim_hash = hash_claim("The mayor announced flood aid.")
        result = {
            "claim_id": 1,
            "verdict": "Partially Verified",
            "message": "Cached test result.",
        }

        save_cached_verdict(
            claim_hash,
            "The mayor announced flood aid.",
            result,
            cache_path=cache_path,
        )
        cached = get_cached_verdict(claim_hash, cache_path=cache_path)
        assert cached["verdict"] == "Partially Verified"

    keyword_result = keyword_overlap_verdict(
        "The Department of Health reported new dengue cases.",
        [
            {
                "source": "GMA News",
                "title": "DOH reports dengue cases",
                "url": "https://example.com/dengue",
                "description": "Health officials report dengue cases.",
                "status": "extracted",
                "text": "The Department of Health reported new dengue cases.",
            }
        ],
    )
    assert keyword_result["verdict"] == "Partially Verified"
    assert keyword_result["keyword_overlap"] > 0

    parsed = _parse_response(
        """
        {
            "verdict": "Not Found",
            "reason": "The evidence discusses flood control projects in Quezon City, but it does not directly confirm flood aid, assistance, relief, or distribution to residents."
        }
        """
    )
    assert parsed["verdict"] == "Not Found"
    assert len(parsed["reason"]) <= 180

    print("All Week 4 helper checks passed.")


if __name__ == "__main__":
    run_checks()
