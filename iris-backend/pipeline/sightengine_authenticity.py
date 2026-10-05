"""SightEngine AI-image assessment for Android /verify-image traffic.

The browser extension asks SightEngine itself and merges the verdict client-side,
so the backend only assesses images from clients that have no check of their own.
Android sends platform: "android" with no credentials of its own; the extension
sends platform: "chrome" and overwrites whatever this module would return, so
asking twice would only burn API quota. Everything unidentified fails closed:
no call, image_authenticity_checked stays False.

The response shape mirrors the extension's analyzeImageAuthenticitySightEngine
exactly, because that is the shape Android already parses: IrisResultData
reads image_authenticity_checked + ai_generated.{status, is_ai_generated,
confidence} and draws NOT_ASSESSED whenever the check did not run or did not
finish. An unassessed image must never be drawn as a cleared one.

No retries, by design: a transient SightEngine failure answers honestly as
NOT_ASSESSED and the next request tries again instead of stacking timeouts
behind an outage.
"""

from __future__ import annotations

import copy
import hashlib
import logging
import math
import os
import threading
import time

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional; plain env vars still work
    def load_dotenv():
        return False

logger = logging.getLogger(__name__)

SIGHTENGINE_API_URL = "https://api.sightengine.com/1.0/check.json"
# Matches the extension's SIGHTENGINE_TIMEOUT_MS so both halves of one check
# give up at the same moment instead of leaving the reader waiting on one.
DEFAULT_TIMEOUT_SECONDS = "30"
# The same models the extension asks for, and the same strictly-greater than
# 0.5 rule: a probability of exactly 0.5 stays "not suspicious" on both sides,
# so backend and client can never disagree about the same image. Deepfake and
# embedded text are returned as independent observations and are never fused
# into the ai_generated verdict -- each reports what that detector saw, and
# none of them is allowed to conclude that an image is authentic.
MODELS = "genai,deepfake,text"
AI_THRESHOLD = 0.5
MAX_CACHE_ENTRIES = 512

_cache_lock = threading.Lock()
_assessment_cache = {}


def _credentials():
    api_user = str(os.getenv("SIGHTENGINE_API_USER", "") or "").strip()
    api_secret = str(os.getenv("SIGHTENGINE_API_SECRET", "") or "").strip()
    return api_user, api_secret


def _failure(error):
    return {
        "image_authenticity_checked": False,
        "ai_generated": {"status": "error", "error": str(error)},
    }


def _cache_get(digest):
    with _cache_lock:
        cached = _assessment_cache.get(digest)
        return copy.deepcopy(cached) if cached is not None else None


def _cache_put(digest, result):
    with _cache_lock:
        if len(_assessment_cache) >= MAX_CACHE_ENTRIES:
            _assessment_cache.clear()
        _assessment_cache[digest] = copy.deepcopy(result)


def _probability(data):
    """Reads SightEngine's `type` as a plain number or an object.

    SightEngine has shipped both shapes: a bare probability and objects such as
    {ai_generated: 0.99} or {probability: 0.99}. Anything unparseable reads as 0,
    the same way the extension reads it — an unknown is not a verdict.
    """
    value = data.get("type", 0) if isinstance(data, dict) else 0
    if isinstance(value, dict):
        value = value.get("ai_generated", value.get("probability", 0))

    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    if not math.isfinite(number):
        return 0.0

    return number


def _detector_probability(container, key):
    """Reads one probability key out of a SightEngine sub-object.

    SightEngine has shipped numbers, missing keys and unparseable strings;
    an unknown reads as 0, the same way the extension reads it -- an unknown
    is an observation of nothing, not a verdict of "clear".
    """
    if not isinstance(container, dict):
        return 0.0

    try:
        number = float(container.get(key, 0))
    except (TypeError, ValueError):
        return 0.0

    if not math.isfinite(number):
        return 0.0

    return number


def _observation(score, is_suspicious, **extra):
    """One detector's reading, in the shape Android's IrisResultData expects.

    Every detector answers with the same fields so a client can render any of
    them without knowing which model produced it. Fields never make one
    detector's output a conclusion about another's.
    """
    payload = {
        "suspicion_score": score,
        "confidence": score,
        "is_suspicious": is_suspicious,
        "model": "SightEngine",
        "status": "ok",
        "error": None,
    }
    payload.update(extra)
    return payload


def _success_result(ai_probability, deepfake_probability, artificial_text, natural_text):
    ai_suspicious = ai_probability > AI_THRESHOLD
    deepfake_suspicious = deepfake_probability > AI_THRESHOLD
    text_suspicious = artificial_text > AI_THRESHOLD

    return {
        "image_authenticity_checked": True,
        "ai_generated": _observation(
            ai_probability, ai_suspicious, is_ai_generated=ai_suspicious,
        ),
        "deepfake": _observation(
            deepfake_probability, deepfake_suspicious, is_deepfake=deepfake_suspicious,
        ),
        # Text present in the scene (has_natural) is not an accusation: only
        # text added after the shot (has_artificial) is flagged.
        "embedded_text": _observation(
            artificial_text,
            text_suspicious,
            has_artificial=artificial_text,
            has_natural=natural_text,
        ),
    }


def assess_image_authenticity(image_bytes):
    """Returns the extension-shaped authenticity verdict for image_bytes.

    Never raises: every failure collapses into image_authenticity_checked: False
    with an error the client renders as the honest "Not assessed" state.
    """
    started_at = time.perf_counter()

    try:
        if not image_bytes:
            return _failure("No image bytes to assess.")

        api_user, api_secret = _credentials()
        if not api_user or not api_secret:
            return _failure("SightEngine credentials not configured.")

        digest = hashlib.sha256(image_bytes).hexdigest()
        cached = _cache_get(digest)
        if cached is not None:
            return cached

        timeout_seconds = float(os.getenv(
            "IRIS_SIGHTENGINE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS,
        ))

        # No retries and no mounted retry adapter: one attempt, one honest answer.
        response = requests.post(
            SIGHTENGINE_API_URL,
            data={
                "models": MODELS,
                "api_user": api_user,
                "api_secret": api_secret,
            },
            files={"media": ("image.jpg", image_bytes, "image/jpeg")},
            timeout=timeout_seconds,
        )

        try:
            data = response.json()
        except ValueError:
            return _failure("SightEngine returned non-JSON response.")

        if not response.ok:
            message = ""
            if isinstance(data, dict):
                message = str(data.get("message") or "")
            return _failure(message or f"SightEngine HTTP {response.status_code}")

        # Deepfake and embedded text live in their own sub-objects; both
        # readers fail closed to 0 when the key is absent or malformed, so a
        # partially-shaped response still yields an honest observation.
        payload_type = data.get("type") if isinstance(data, dict) else {}
        payload_text = data.get("text") if isinstance(data, dict) else {}
        result = _success_result(
            _probability(data),
            _detector_probability(payload_type, "deepfake"),
            _detector_probability(payload_text, "has_artificial"),
            _detector_probability(payload_text, "has_natural"),
        )
        # Only finished, successful checks are cached: a timeout or outage must
        # be asked again next time instead of being remembered as truth.
        _cache_put(digest, result)
        return result
    except requests.RequestException as error:
        return _failure(f"SightEngine request failed: {error}")
    except Exception as error:  # pragma: no cover - belt and braces: never raise
        return _failure(f"SightEngine check failed: {error}")
    finally:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info("SightEngine check finished in %d ms.", elapsed_ms)
