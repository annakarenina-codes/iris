"""SightEngine stays honest for Android images: one shot, hashed cache, no fake verdicts.

Two layers are covered: the module contract (response shape identical to the
extension's analyzer, threshold semantics, no retries, cache rules) and the
route contract (only platform "android" ever starts a check; every response
path carries the result; unidentified traffic fails closed).
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

import pipeline.sightengine_authenticity as sightengine
from pipeline.sightengine_authenticity import assess_image_authenticity

CREDS = {"SIGHTENGINE_API_USER": "test-user", "SIGHTENGINE_API_SECRET": "test-secret"}
IMAGE = b"image-bytes-for-unit-tests"

# A complete 1x1 PNG: decode_base64_image validates real image bytes, so route
# tests must send something that survives validation.
PNG_BASE64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def success_payload():
    """The success shape the extension produces and Android's IrisResultData parses."""
    return {
        "image_authenticity_checked": True,
        "ai_generated": {
            "suspicion_score": 0.99,
            "confidence": 0.99,
            "is_suspicious": True,
            "is_ai_generated": True,
            "model": "SightEngine",
            "status": "ok",
            "error": None,
        },
    }


def http_response(ok=True, status_code=200, json_value=None, json_error=None):
    response = MagicMock()
    response.ok = ok
    response.status_code = status_code
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = {} if json_value is None else json_value
    return response


class AssessAuthenticityTests(unittest.TestCase):
    def setUp(self):
        sightengine._assessment_cache.clear()

    def assess(self, post_value=None, post_side_effect=None, env=None):
        environ = env if env is not None else CREDS
        with patch.dict(os.environ, environ, clear=True):
            with patch.object(
                sightengine.requests, "post",
                return_value=post_value, side_effect=post_side_effect,
            ) as post:
                result = assess_image_authenticity(IMAGE)
        return result, post

    def test_high_probability_is_ai_generated_in_the_extension_shape(self):
        result, post = self.assess(post_value=http_response(json_value={"type": 0.99}))

        self.assertTrue(result["image_authenticity_checked"])
        ai = result["ai_generated"]
        self.assertEqual(ai["status"], "ok")
        self.assertTrue(ai["is_ai_generated"])
        self.assertTrue(ai["is_suspicious"])
        self.assertEqual(ai["confidence"], 0.99)
        self.assertEqual(ai["model"], "SightEngine")
        self.assertIsNone(ai["error"])
        post.assert_called_once()

    def test_probability_exactly_half_stays_not_suspicious(self):
        # Strictly greater than 0.5, same rule as the extension: the two sides
        # can never disagree about the same image.
        result, _ = self.assess(post_value=http_response(json_value={"type": 0.5}))

        self.assertTrue(result["image_authenticity_checked"])
        self.assertFalse(result["ai_generated"]["is_ai_generated"])
        self.assertEqual(result["ai_generated"]["confidence"], 0.5)

    def test_object_shaped_type_is_read_both_ways_sightengine_ships(self):
        for shaped in ({"type": {"ai_generated": 0.7}}, {"type": {"probability": 0.7}}):
            with self.subTest(shape=shaped):
                sightengine._assessment_cache.clear()
                result, _ = self.assess(post_value=http_response(json_value=shaped))

                self.assertTrue(result["image_authenticity_checked"])
                self.assertTrue(result["ai_generated"]["is_ai_generated"])
                self.assertEqual(result["ai_generated"]["confidence"], 0.7)

    def test_unparseable_probability_reads_as_zero_not_as_a_verdict(self):
        result, _ = self.assess(post_value=http_response(json_value={"type": "broken"}))

        self.assertTrue(result["image_authenticity_checked"])
        self.assertFalse(result["ai_generated"]["is_ai_generated"])
        self.assertEqual(result["ai_generated"]["confidence"], 0.0)

    def test_missing_type_reads_as_zero(self):
        result, _ = self.assess(post_value=http_response(json_value={}))

        self.assertTrue(result["image_authenticity_checked"])
        self.assertFalse(result["ai_generated"]["is_ai_generated"])

    def test_non_json_answer_is_not_assessed(self):
        result, post = self.assess(post_value=http_response(json_error=ValueError("no json")))

        self.assertFalse(result["image_authenticity_checked"])
        self.assertEqual(result["ai_generated"]["status"], "error")
        self.assertIn("non-JSON", result["ai_generated"]["error"])
        post.assert_called_once()

    def test_http_error_reports_the_api_message(self):
        result, _ = self.assess(
            post_value=http_response(ok=False, status_code=429,
                                     json_value={"message": "quota exceeded"}),
        )

        self.assertFalse(result["image_authenticity_checked"])
        self.assertEqual(result["ai_generated"]["error"], "quota exceeded")

    def test_missing_credentials_never_calls_the_api(self):
        result, post = self.assess(env={})

        self.assertFalse(result["image_authenticity_checked"])
        self.assertIn("credentials", result["ai_generated"]["error"])
        post.assert_not_called()

    def test_network_errors_never_raise(self):
        result, _ = self.assess(post_side_effect=requests.Timeout("too slow"))

        self.assertFalse(result["image_authenticity_checked"])
        self.assertEqual(result["ai_generated"]["status"], "error")

    def test_empty_bytes_never_call_the_api(self):
        with patch.object(sightengine.requests, "post") as post:
            result = assess_image_authenticity(b"")

        self.assertFalse(result["image_authenticity_checked"])
        post.assert_not_called()

    def test_same_bytes_are_only_asked_once(self):
        result_one, post = self.assess(post_value=http_response(json_value={"type": 0.9}))

        # Cache from the first call stays warm; the second call must not ask again.
        with patch.dict(os.environ, CREDS, clear=True):
            with patch.object(sightengine.requests, "post",
                              return_value=http_response(json_value={"type": 0.1})) as post_two:
                result_two = assess_image_authenticity(IMAGE)

        # First session cached the 0.9 answer; the second call must not ask again.
        self.assertEqual(post.call_count, 1)
        post_two.assert_not_called()
        self.assertEqual(result_one, result_two)
        self.assertEqual(result_two["ai_generated"]["confidence"], 0.9)

    def test_failed_checks_are_not_cached(self):
        _, post = self.assess(
            post_value=http_response(ok=False, status_code=500, json_value={}),
        )
        post.assert_called_once()

        result, post_two = self.assess(post_value=http_response(json_value={"type": 0.9}))
        post_two.assert_called_once()
        self.assertTrue(result["image_authenticity_checked"])


def _ocr_ok(text="The mayor announced the flood control project."):
    return {
        "status": "ok",
        "text": text,
        "confidence": 0.9,
        "word_count": 8,
        "low_confidence": False,
        "warnings": [],
        "regions": [],
    }


def _ocr_no_text():
    return {
        "status": "no_text",
        "text": "",
        "confidence": 0.0,
        "word_count": 0,
        "low_confidence": True,
        "warnings": ["No text found."],
        "regions": [],
    }


class VerifyImageAuthenticityRouteTests(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app
        self.client = app.app.test_client()

    def post(self, payload, assess_result=None, ocr=None):
        ocr_result = ocr if ocr is not None else _ocr_ok()
        with patch.object(self.app, "extract_text_from_image", return_value=ocr_result), \
             patch.object(self.app, "verify_text_payload",
                          return_value={"verdict": "Verified"}), \
             patch.object(self.app, "assess_image_authenticity",
                          return_value=assess_result if assess_result is not None else success_payload(),
                          ) as assess:
            response = self.client.post("/verify-image", json=payload)
        return response, assess

    def test_android_traffic_gets_assessed_and_carries_the_verdict(self):
        response, assess = self.post(
            {"image_base64": PNG_BASE64, "platform": "android"},
        )

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        assess.assert_called_once()
        self.assertTrue(body["image_authenticity_checked"])
        self.assertTrue(body["ai_generated"]["is_ai_generated"])
        self.assertEqual(body["ai_generated"]["status"], "ok")

    def test_chrome_extension_traffic_is_never_asked_twice(self):
        response, assess = self.post(
            {"image_base64": PNG_BASE64, "platform": "chrome"},
        )

        body = response.get_json()
        assess.assert_not_called()
        self.assertFalse(body["image_authenticity_checked"])

    def test_unidentified_traffic_fails_closed(self):
        response, assess = self.post({"image_base64": PNG_BASE64})

        body = response.get_json()
        assess.assert_not_called()
        self.assertFalse(body["image_authenticity_checked"])

    def test_android_failure_lands_as_honest_not_assessed(self):
        failure = {
            "image_authenticity_checked": False,
            "ai_generated": {"status": "error", "error": "SightEngine request failed."},
        }
        response, _ = self.post(
            {"image_base64": PNG_BASE64, "platform": "android"},
            assess_result=failure,
        )

        body = response.get_json()
        self.assertFalse(body["image_authenticity_checked"])
        self.assertEqual(body["ai_generated"]["status"], "error")

    def test_the_badge_survives_an_ocr_failure(self):
        response, assess = self.post(
            {"image_base64": PNG_BASE64, "platform": "android"},
            ocr=_ocr_no_text(),
        )

        body = response.get_json()
        assess.assert_called_once()
        self.assertTrue(body["image_authenticity_checked"])
        self.assertEqual(body["ocr_status"], "no_text")

    def test_a_undecodable_image_is_never_sent_to_sightengine(self):
        response, assess = self.post(
            {"image_base64": "not-an-image", "platform": "android"},
        )

        body = response.get_json()
        assess.assert_not_called()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(body["image_authenticity_checked"])


class DetectorObservationTests(unittest.TestCase):
    """Deepfake and embedded text are independent observations, never a fusion.

    Each detector reports only what that detector saw. None of them is allowed to
    conclude anything about the others, and none may conclude an image is authentic.
    """

    def setUp(self):
        sightengine._assessment_cache.clear()

    def assess(self, json_value):
        with patch.dict(os.environ, CREDS, clear=True):
            with patch.object(
                sightengine.requests, "post",
                return_value=http_response(json_value=json_value),
            ) as post:
                result = assess_image_authenticity(IMAGE)
        return result, post

    def test_the_three_models_ride_one_request(self):
        _, post = self.assess(json_value={"type": {"ai_generated": 0.1}})

        self.assertEqual(post.call_args.kwargs["data"]["models"], "genai,deepfake,text")

    def test_each_detector_reports_only_its_own_reading(self):
        result, _ = self.assess(json_value={
            "type": {"ai_generated": 0.001, "deepfake": 0.82},
            "text": {"has_artificial": 0.91, "has_natural": 0.05},
        })

        # Three verdicts, no fusion: a deepfake flag must not drag genai up with it.
        self.assertFalse(result["ai_generated"]["is_suspicious"])
        self.assertEqual(result["ai_generated"]["suspicion_score"], 0.001)

        self.assertTrue(result["deepfake"]["is_suspicious"])
        self.assertTrue(result["deepfake"]["is_deepfake"])
        self.assertEqual(result["deepfake"]["suspicion_score"], 0.82)

        self.assertTrue(result["embedded_text"]["is_suspicious"])
        self.assertEqual(result["embedded_text"]["has_artificial"], 0.91)

    def test_detector_at_exactly_half_stays_not_suspicious(self):
        # Same strictly-greater-than-0.5 rule as ai_generated, so backend, extension
        # and Android can never disagree about the same image.
        result, _ = self.assess(json_value={
            "type": {"ai_generated": 0.1, "deepfake": 0.5},
            "text": {"has_artificial": 0.5, "has_natural": 0.5},
        })

        self.assertFalse(result["deepfake"]["is_suspicious"])
        self.assertFalse(result["embedded_text"]["is_suspicious"])

    def test_text_in_the_scene_is_not_an_accusation(self):
        # A storefront sign is natural text. Only text added after the shot is flagged.
        result, _ = self.assess(json_value={
            "type": {"ai_generated": 0.1},
            "text": {"has_artificial": 0.001, "has_natural": 0.93},
        })

        embedded = result["embedded_text"]
        self.assertFalse(embedded["is_suspicious"])
        self.assertEqual(embedded["has_natural"], 0.93)
        self.assertEqual(embedded["has_artificial"], 0.001)

    def test_missing_detector_keys_still_yield_a_full_observation(self):
        result, _ = self.assess(json_value={"type": {"ai_generated": 0.9}})

        # Absent keys read as 0 rather than raising: a partially-shaped 200 still
        # answers, and every observation carries the same fields either way.
        self.assertFalse(result["deepfake"]["is_suspicious"])
        self.assertEqual(result["deepfake"]["suspicion_score"], 0.0)
        self.assertEqual(result["deepfake"]["model"], "SightEngine")
        self.assertFalse(result["embedded_text"]["is_suspicious"])
        self.assertEqual(result["embedded_text"]["has_natural"], 0.0)

    def test_a_failed_check_does_not_grow_the_new_keys(self):
        with patch.dict(os.environ, CREDS, clear=True):
            with patch.object(
                sightengine.requests, "post",
                return_value=http_response(ok=False, status_code=500, json_value={}),
            ):
                result = assess_image_authenticity(IMAGE)

        # An unassessed image must not gain empty verdicts for detectors that never
        # ran: absent stays absent, checked stays False, and the failure rides only
        # where every surface already knows to read it.
        self.assertFalse(result["image_authenticity_checked"])
        self.assertNotIn("deepfake", result)
        self.assertNotIn("embedded_text", result)
        self.assertEqual(result["ai_generated"]["status"], "error")

    def test_every_observation_carries_the_same_fields(self):
        result, _ = self.assess(json_value={
            "type": {"ai_generated": 0.4, "deepfake": 0.4},
            "text": {"has_artificial": 0.4, "has_natural": 0.4},
        })

        expected = {"suspicion_score", "confidence", "is_suspicious", "model",
                    "status", "error"}
        for key in ("ai_generated", "deepfake", "embedded_text"):
            with self.subTest(detector=key):
                self.assertTrue(expected <= set(result[key]), result[key])
                self.assertEqual(result[key]["model"], "SightEngine")
                self.assertEqual(result[key]["status"], "ok")
                self.assertIsNone(result[key]["error"])
                self.assertEqual(result[key]["confidence"],
                                 result[key]["suspicion_score"])


if __name__ == "__main__":
    unittest.main()
