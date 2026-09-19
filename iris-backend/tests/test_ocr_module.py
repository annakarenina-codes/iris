"""
OCR module and /verify-image endpoint checks.

These tests avoid calling EasyOCR directly so they can run before the heavy OCR
dependencies are installed.
"""

from pathlib import Path
from io import BytesIO
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app as iris_app
from pipeline.ocr import decode_base64_image, validate_image_bytes


PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _fake_content_profile(text, translated):
    return {
        "status": "ok",
        "method": "test_stub",
        "error": None,
        "post_type": "fact_only",
        "confidence": 0.90,
        "ambiguity_score": 0.0,
        "ambiguity_reasons": [],
        "contains_factual_claims": True,
        "contains_opinion": False,
        "contains_recommendation": False,
        "contains_forecast_or_projection": False,
        "contains_satire_or_humor": False,
        "contains_quote": False,
        "eligible_for_verification": True,
        "recommended_route": "proceed_to_verification",
        "verification_text": text,
        "normalized_verification_text": translated,
        "segments": [],
        "ignored_segments": [],
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
                "description": "DOH reported dengue cases.",
                "status": "extracted",
                "word_count": 80,
                "error": None,
                "text": "The Department of Health reported 1,000 dengue cases in July 2026.",
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
    evidence = {
        "source": "GMA News",
        "title": "DOH reports dengue cases",
        "url": "https://example.com/dengue",
        "similarity_score": 0.91,
        "status": "extracted",
        "word_count": 80,
    }

    return {
        "verdict": "Verified",
        "reason": "Fake OCR endpoint verdict.",
        "corroboration_count": 1,
        "primary_evidence": evidence,
        "supporting_sources": [evidence],
        "similarity_thresholds": {
            "verified": 0.85,
            "partial": 0.5,
        },
    }


def _fake_ocr_ok(image_bytes):
    text = "The Department of Health reported 1,000 dengue cases in July 2026."
    return {
        "status": "ok",
        "text": text,
        "word_count": 11,
        "confidence": 0.88,
        "low_confidence": False,
        "warnings": [],
        "error": None,
        "image": {
            "byte_size": len(image_bytes),
            "format": "png",
        },
        "regions": [
            {
                "text": text,
                "confidence": 0.88,
                "bbox": [[0, 0], [10, 0], [10, 10], [0, 10]],
            }
        ],
        "image_authenticity_checked": False,
    }


def _fake_ocr_missing_dependency(image_bytes):
    return {
        "status": "missing_dependency",
        "text": "",
        "word_count": 0,
        "confidence": None,
        "low_confidence": True,
        "warnings": ["Missing OCR dependencies: easyocr, Pillow."],
        "error": "Missing OCR dependencies: easyocr, Pillow.",
        "image": {
            "byte_size": len(image_bytes),
            "format": "png",
        },
        "regions": [],
        "image_authenticity_checked": False,
    }


class _FakeImageResponse:
    def __init__(self, body, content_type="image/png", status_code=200):
        self.body = body
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(body)),
        }
        self.status_code = status_code

    def iter_content(self, chunk_size=65536):
        yield self.body

    def close(self):
        pass


def run_checks() -> None:
    decoded = decode_base64_image(f"data:image/png;base64,{PNG_BASE64}")
    assert decoded["status"] == "ok"
    assert decoded["image_format"] == "png"

    invalid = decode_base64_image("not base64")
    assert invalid["status"] == "invalid_base64"

    unsupported = validate_image_bytes(b"not an image")
    assert unsupported["status"] == "unsupported_image_type"

    original_requests_get = iris_app.requests.get
    originals = {
        "detect_language": iris_app.detect_language,
        "translate_to_english": iris_app.translate_to_english,
        "profile_content": iris_app.profile_content,
        "is_opinion": iris_app.is_opinion,
        "flag_political": iris_app.flag_political,
        "extract_claims": iris_app.extract_claims,
        "search_and_extract": iris_app.search_and_extract,
        "generate_verdict": iris_app.generate_verdict,
        "refine_with_openai_rag": iris_app.refine_with_openai_rag,
        "get_cached_verdict": iris_app.get_cached_verdict,
        "save_cached_verdict": iris_app.save_cached_verdict,
        "extract_text_from_image": iris_app.extract_text_from_image,
    }

    try:
        iris_app.detect_language = lambda text: "english"
        iris_app.translate_to_english = lambda text, language: text
        iris_app.profile_content = _fake_content_profile
        iris_app.is_opinion = lambda text: {
            "is_opinion": False,
            "matched_phrases": [],
            "matched_words": [],
        }
        iris_app.flag_political = lambda text: {
            "politically_sensitive": False,
            "matched_keywords": [],
            "matched_agencies": [],
            "matched_categories": {},
        }
        iris_app.extract_claims = lambda text, translated: {
            "status": "ok",
            "method": "test_stub",
            "error": None,
            "post_type": "fact_only",
            "contains_opinion": False,
            "contains_recommendation": False,
            "ignored_segments": [],
            "claims": [
                {
                    "claim_id": 1,
                    "claim_text": text,
                    "normalized_claim": translated,
                    "claim_type": "factual_claim",
                    "risk_tags": [],
                }
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
        iris_app.extract_text_from_image = _fake_ocr_ok

        client = iris_app.app.test_client()
        response = client.post(
            "/verify-image",
            json={
                "image_base64": PNG_BASE64,
                "debug": True,
            },
        )
        payload = response.get_json()

        assert response.status_code == 200
        assert payload["input_type"] == "image"
        assert payload["ocr_status"] == "ok"
        assert payload["ocr_text"].startswith("The Department of Health")
        assert payload["image_authenticity_checked"] is False
        assert payload["verdict"] == "Verified"
        assert payload["claim_count"] == 1
        assert "ocr" in payload["debug"]

        multipart_response = client.post(
            "/verify-image",
            data={
                "image": (BytesIO(decoded["image_bytes"]), "claim.png"),
                "debug": "true",
            },
            content_type="multipart/form-data",
        )
        multipart_payload = multipart_response.get_json()

        assert multipart_response.status_code == 200
        assert multipart_payload["input_type"] == "image"
        assert multipart_payload["ocr_status"] == "ok"
        assert "ocr" in multipart_payload["debug"]

        iris_app.requests.get = lambda url, **kwargs: _FakeImageResponse(decoded["image_bytes"])
        url_response = client.post(
            "/verify-image",
            json={
                "image_url": "https://example.com/claim.png",
                "debug": True,
            },
        )
        url_payload = url_response.get_json()

        assert url_response.status_code == 200
        assert url_payload["input_type"] == "image"
        assert url_payload["ocr_status"] == "ok"
        assert url_payload["ocr_text"].startswith("The Department of Health")

        iris_app.requests.get = lambda url, **kwargs: _FakeImageResponse(
            b"<html>not an image</html>",
            content_type="text/html",
        )
        non_image_response = client.post(
            "/verify-image",
            json={"image_url": "https://example.com/not-image"},
        )
        non_image_payload = non_image_response.get_json()

        assert non_image_response.status_code == 400
        assert non_image_payload["ocr_status"] == "unsupported_image_type"

        bad_response = client.post(
            "/verify-image",
            json={"image_base64": "not base64"},
        )
        bad_payload = bad_response.get_json()

        assert bad_response.status_code == 400
        assert bad_payload["ocr_status"] == "invalid_base64"

        iris_app.extract_text_from_image = _fake_ocr_missing_dependency
        missing_response = client.post(
            "/verify-image",
            json={"image_base64": PNG_BASE64},
        )
        missing_payload = missing_response.get_json()

        assert missing_response.status_code == 503
        assert missing_payload["verdict"] == "OCR Unavailable"
        assert missing_payload["ocr_status"] == "missing_dependency"
    finally:
        for name, value in originals.items():
            setattr(iris_app, name, value)
        iris_app.requests.get = original_requests_get

    print("All OCR module checks passed.")


if __name__ == "__main__":
    run_checks()
