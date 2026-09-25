"""Regression checks for the pre-verdict failures in the solo TRACE review."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import content_profiler as profiler
from pipeline import translator


CASES = json.loads((Path(__file__).parent / "fixtures" / "screening_trace_cases.json")
                   .read_text(encoding="utf-8"))
TEXTS = {case["case"]: case["text"] for case in CASES}
ERROR_PAGE = "Error 500 (Server Error)!!1500.That's an error. Please try again later."


@pytest.fixture(autouse=True)
def translation_configuration(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key-not-live')
    monkeypatch.setattr(translator, 'AsyncOpenAI', Mock())


@pytest.mark.parametrize("value", [
    None, "", " \n", {}, [], 500, ERROR_PAGE,
    "<!doctype html><html><body>Service error</body></html>",
    "HTTP 503 Service Unavailable", "Too Many Requests",
    '{"error": "quota exceeded"}', '{"status": 500, "message": "failed"}',
])
def test_failed_translation_preserves_original_and_records_reason(value):
    with patch.object(translator, "event") as event:
        assert translator.sanitize_translation(TEXTS[9], value) == TEXTS[9]
    assert event.call_args.args == ("translation.fallback",)
    assert event.call_args.kwargs["action"] == "preserve_original"


def test_valid_translation_and_english_bypass():
    translated = "The peso closed at 62.513 per dollar on Wednesday."
    with patch.object(translator, "_request_translation", new_callable=AsyncMock) as provider:
        provider.return_value = translated
        assert translator.translate_to_english(TEXTS[9], "tagalog") == translated
        provider.assert_awaited_once()
        provider.reset_mock()
        assert translator.translate_to_english(TEXTS[4], "english") == TEXTS[4]
        provider.assert_not_called()


@pytest.mark.parametrize("failure", [ERROR_PAGE, RuntimeError("provider unavailable")])
def test_provider_failures_do_not_escape_as_claim_text(failure):
    with patch.object(translator, "_request_translation", new_callable=AsyncMock) as provider:
        if isinstance(failure, Exception):
            provider.side_effect = failure
        else:
            provider.return_value = failure
        assert translator.translate_to_english(TEXTS[9], "tagalog") == TEXTS[9]


def test_console_encoding_cannot_change_a_successful_translation():
    with patch.object(translator, "_request_translation", new_callable=AsyncMock) as provider, patch(
        "builtins.print", side_effect=UnicodeEncodeError("charmap", "\u20b1", 0, 1, "unsupported")
    ):
        provider.return_value = "The rate is 62.513 per dollar."
        assert translator.translate_to_english(TEXTS[9], "tagalog") == "The rate is 62.513 per dollar."


def test_original_posts_about_server_errors_are_not_erased():
    text = "Error 500 affected the municipal website yesterday."
    assert translator.sanitize_translation(text, text) == text
    assert translator.sanitize_translation(text, "The website reported error 500 yesterday.") != text


@pytest.mark.parametrize("number", [4, 6, 9, 10])
def test_uncertain_but_checkable_trace_inputs_reach_extraction_without_ai(number):
    profile = profiler.profile_content(TEXTS[number], ERROR_PAGE, use_ai=False)
    assert profile["eligible_for_verification"]
    assert ERROR_PAGE not in json.dumps(profile)
    assert profile["normalized_verification_text"] == profile["verification_text"]
    for segment in profile["segments"]:
        assert segment["text"] in TEXTS[number]
        if segment["eligible_for_verification"]:
            assert segment["text"] in profile["verification_text"]


def test_weak_scores_do_not_drop_edsa_factual_paragraphs():
    profile = profiler.profile_content(TEXTS[6], use_ai=False)
    for detail in ["lubak", "24 Oras", "P1.2 bilyon", "Jay Sonza", "wala pang"]:
        assert detail in profile["verification_text"]


def test_numeric_amount_negation_and_imaginary_qualifier_are_preserved():
    for number, detail in [(1, "imaginary"), (4, "doesn\u2019t"), (9, "\u20b162.513")]:
        profile = profiler.profile_content(TEXTS[number], use_ai=False)
        assert detail in profile["verification_text"]


@pytest.mark.parametrize("text,route", [
    ("Sa tingin ko, masama ang bagong policy.", "stop_opinion_detected"),
    ("The economy will collapse next year.", "stop_forecast_projection"),
    ("Please share this with all your friends.", "stop_opinion_detected"),
    ("haha lol this is a joke", "stop_no_checkable_claims"),
    ("HAVE YOU ALREADY VISITED BARMM?", "stop_no_checkable_claims"),
])
def test_clear_nonclaims_are_still_skipped(text, route):
    profile = profiler.profile_content(text, use_ai=False)
    assert not profile["eligible_for_verification"]
    assert profile["recommended_route"] == route


def test_scheduled_announcement_is_not_forecast_accuracy():
    text = "Ten artists will be proclaimed tomorrow."
    assert profiler.profile_content(text, use_ai=False)["eligible_for_verification"]


def test_mixed_post_keeps_fact_and_excludes_opinion():
    text = "The Department of Health reported 100 cases. This administration is useless."
    profile = profiler.profile_content(text, use_ai=False)
    assert "reported 100 cases" in profile["verification_text"]
    assert "useless" not in profile["verification_text"]


def test_positive_ai_advice_is_not_vetoed_by_zero_confidence():
    local = profiler._local_profile(TEXTS[4], None)
    local["segments"][0]["eligible_for_verification"] = False
    advice = {"used": True, "status": "ok", "result": {"segments": [{
        "segment_id": "s1", "top_label": "factual_claim", "top_label_score": 0.0,
        "eligible_for_verification": True, "text": "Invented replacement",
    }]}}
    result = profiler._merge_openai_segment_advice(local, advice)
    assert result["eligible_for_verification"]
    assert result["verification_text"] == TEXTS[4]
    assert "openai_factual_claim_advice" in result["segments"][0]["reason_codes"]


@pytest.mark.parametrize("result", [None, [], {"segments": None}, {"segments": "bad"},
    {"segments": [{"segment_id": "unknown", "top_label": "factual_claim", "eligible_for_verification": True}]},
    {"segments": [{"segment_id": "s1", "top_label": "factual_claim", "eligible_for_verification": "false"}]},
])
def test_malformed_or_unmatched_advice_does_not_promote_clear_opinion(result):
    local = profiler._local_profile("In my opinion this is the worst idea.", None)
    merged = profiler._merge_openai_segment_advice(local, {"result": result})
    assert not merged["eligible_for_verification"]


def test_unavailable_advisor_does_not_discard_possible_claims():
    with patch.object(profiler, "_request_openai_profile", return_value={
        "used": False, "status": "error", "error": "provider unavailable", "result": None,
    }):
        profile = profiler.profile_content(TEXTS[10])
    assert profile["eligible_for_verification"]
    assert profile["openai_profile"]["status"] == "error"


@pytest.mark.parametrize("number", [4, 6, 9, 10])
def test_application_passes_original_claim_candidates_to_extractor(number):
    import app as iris

    class ReachedExtraction(Exception):
        pass

    extractor = Mock(side_effect=ReachedExtraction)
    with patch.object(iris, "detect_language", return_value="taglish"), \
         patch.object(translator, "_request_translation", new_callable=AsyncMock) as provider, \
         patch.object(iris, "profile_content", side_effect=lambda text, translated:
                      profiler.profile_content(text, translated, use_ai=False)), \
         patch.object(iris, "extract_claims", extractor):
        provider.return_value = ERROR_PAGE
        with pytest.raises(ReachedExtraction):
            iris.verify_text_payload(TEXTS[number])
    source, normalized = extractor.call_args.args
    assert source and source == normalized
    assert ERROR_PAGE not in source
