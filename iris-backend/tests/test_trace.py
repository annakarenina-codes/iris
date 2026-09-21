import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as iris
from iris_trace.core import (
    CURRENT,
    Trace,
    Store,
    StopAfter,
    TargetNotReached,
    ReplayMissing,
    safe,
    traced,
    submit_context,
)
from iris_trace.calibration import run_case, validate_case
from iris_trace.web import store_for


@pytest.fixture
def app(tmp_path):
    iris.app.config.update(
        TESTING=True,
        IRIS_TRACE_ENABLED=True,
        IRIS_TRACE_PATH=str(tmp_path / "trace.sqlite3"),
        IRIS_TRACE_TOKEN=None,
        IRIS_TRACE_ARTIFACTS=True,
    )
    yield iris.app
    store = iris.app.extensions.pop("iris_trace_store", None)
    if store:
        store.flush()
        store.close()
    iris.app.config.update(IRIS_TRACE_ENABLED=False, TESTING=False)


def snapshot(app, trace_id):
    s = store_for(app)
    assert s.flush()
    return s.get(trace_id)


def test_disabled_does_not_create_storage_or_expose_routes(app, tmp_path):
    app.config["IRIS_TRACE_ENABLED"] = False
    with app.test_client() as client:
        response = client.post("/verify", json={"text": "", "debug": True})
        assert response.status_code == 400
        assert "X-IRIS-Trace-ID" not in response.headers
        assert client.get("/debug/trace").status_code == 404
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("body", [{}, {"text": ""}, {"text": None}, ["wrong shape"]])
def test_rejected_and_exception_requests_survive(app, body):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    with app.test_client() as client:
        response = client.post("/verify", json=body)
    trace = snapshot(app, response.headers["X-IRIS-Trace-ID"])
    assert trace["status"] in {"error", "rejected"}
    assert any(e.get("stage_id") == "request.parse_validate" for e in trace["events"])
    assert trace["events"][-1]["kind"] == "request.result"
    assert CURRENT.get() is None


def test_malformed_json_keeps_http_contract(app):
    with app.test_client() as client:
        response = client.post("/verify", data="{", content_type="application/json")
    assert response.status_code == 400
    assert snapshot(app, response.headers["X-IRIS-Trace-ID"])["status"] == "rejected"


def test_error_dictionary_is_not_hidden_by_completed_call(app):
    with app.test_client() as client:
        response = client.post("/verify-image", json={"image_base64": "not an image"})
    trace = snapshot(app, response.headers["X-IRIS-Trace-ID"])
    spans = [e for e in trace["events"] if e["kind"] == "span.end"]
    assert any(e.get("domain_outcome") not in {None, "ok"} for e in spans)
    assert trace["status"] == "rejected"


def test_multi_claim_response_is_unchanged_and_scoped(app):
    from test_week4_app import _fake_content_profile, _fake_search_result

    extracted = {
        "status": "ok",
        "claims": [
            {
                "claim_id": str(i),
                "claim_text": f"DOH reports dengue cases {i}.",
                "normalized_claim": f"DOH reports dengue cases {i}.",
            }
            for i in (1, 2)
        ],
        "contains_opinion": False,
        "contains_recommendation": False,
        "ignored_segments": [],
    }
    with patch('pipeline.component_evidence.review_components', return_value={
        'status': 'ok', 'verdict': 'Not Found', 'supporting_urls': [],
        'components': [{'status': 'not_supported'}], 'reason': 'Deterministic trace test.',
    }), patch.multiple(
        iris,
        detect_language=lambda t: "english",
        translate_to_english=lambda t, l: t,
        profile_content=lambda t, tr: _fake_content_profile(t, tr),
        extract_claims=lambda *a: extracted,
        search_and_extract=lambda **kw: _fake_search_result(),
        get_cached_verdict=lambda *a: None,
        save_cached_verdict=lambda *a: None,
    ):
        with app.test_client() as client:
            app.config["IRIS_TRACE_ENABLED"] = False
            expected = client.post(
                "/verify", json={"text": "DOH reports dengue cases."}
            ).get_json()
            app.config["IRIS_TRACE_ENABLED"] = True
            response = client.post(
                "/verify",
                json={"text": "DOH reports dengue cases.", "platform": "chrome"},
            )
    assert response.get_json() == expected
    trace = snapshot(app, response.headers["X-IRIS-Trace-ID"])
    assert trace["claim_count"] == 2 and trace["platform"] == "chrome"
    assert {
        e["claim_id"] for e in trace["events"] if e.get("stage_id") == "claim.process"
    } == {"1", "2"}
    assert len([e for e in trace["events"] if e["kind"] == "claim.final"]) == 2


def test_active_concurrent_requests_and_worker_context_are_isolated(app):
    s = store_for(app)
    gate = threading.Event()

    @traced("retrieval.source_search")
    def source(value):
        gate.wait(2)
        return {"value": value, "status": "error"}

    def worker(value):
        trace = Trace(s, "/verify", {"text": value})
        token = CURRENT.set(trace)
        try:
            with ThreadPoolExecutor(1) as pool:
                assert submit_context(pool, source, value).result()["value"] == value
            trace.finish({"verdict": value})
        finally:
            CURRENT.reset(token)
        return trace.id

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(worker, v) for v in ("A", "B")]
        until = time.time() + 2
        while time.time() < until:
            s.flush()
            if len(s.list()["items"]) == 2:
                break
        active = s.list()["items"]
        assert len(active) == 2 and all(x["status"] == "running" for x in active)
        gate.set()
        ids = [f.result() for f in futures]
    for trace_id in ids:
        trace = snapshot(app, trace_id)
        values = [
            e["output"]["value"] for e in trace["events"] if e["kind"] == "span.end"
        ]
        assert values == [trace["title"]]


def test_input_summaries_are_snapshots_and_redacted():
    data = {
        "password": "hidden",
        "url": "https://user:pass@example.com/a?token=hidden",
        "image_base64": "SECRET_IMAGE",
        "items": [1],
    }
    copied = safe(data)
    data["items"].append(2)
    assert copied["items"] == [1]
    encoded = json.dumps(copied)
    assert (
        "hidden" not in encoded
        and "SECRET_IMAGE" not in encoded
        and "user:pass" not in encoded
    )
    assert copied["url"] == "https://example.com/a"


def test_cache_bypass_never_reads_or_writes_cache(app):
    from pipeline.cache import get_cached_verdict, save_cached_verdict

    trace = Trace(store_for(app), "/calibration", cache_bypass=True)
    token = CURRENT.set(trace)
    try:
        with patch(
            "pipeline.cache.init_cache", side_effect=AssertionError("cache touched")
        ):
            assert get_cached_verdict("abc") is None
            save_cached_verdict("abc", "claim", {})
    finally:
        trace.finish()
        CURRENT.reset(token)


def test_partial_layout_does_not_run_downstream(app):
    from pipeline.ocr_layout import select_content_regions

    trace = Trace(store_for(app), "/calibration", stop_after="image.layout")
    token = CURRENT.set(trace)
    try:
        with pytest.raises(StopAfter):
            select_content_regions([])
        assert trace.target_reached
    finally:
        trace.finish()
        CURRENT.reset(token)
    assert snapshot(app, trace.id)["status"] == "partial"


def test_missing_replay_response_never_calls_dependency(app):
    called = []

    @traced("dependency", dependency=True)
    def dependency(x):
        called.append(x)
        return x

    trace = Trace(store_for(app), "/calibration")
    trace.replay = {}
    token = CURRENT.set(trace)
    try:
        with pytest.raises(ReplayMissing):
            dependency("input")
        assert not called and trace.replay_missing
    finally:
        trace.finish()
        CURRENT.reset(token)


def test_safe_capture_failure_does_not_replace_result(app):
    store = store_for(app)

    @traced("example")
    def operation():
        return {"result": 7}

    trace = Trace(store, "/verify")
    token = CURRENT.set(trace)
    try:
        with patch.object(store, "submit", side_effect=OSError("disk failed")):
            assert operation() == {"result": 7}
        assert trace.partial
    finally:
        trace.finish()
        CURRENT.reset(token)


def test_routes_protect_history_and_mutations(app):
    with app.test_client() as client:
        assert (
            client.get(
                "/debug/traces", environ_overrides={"REMOTE_ADDR": "192.0.2.5"}
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/debug/traces", headers={"Host": "attacker.example"}
            ).status_code
            == 403
        )
        assert client.post("/debug/calibration/runs", json={}).status_code == 403
        assert (
            client.post(
                "/debug/calibration/runs",
                json={},
                headers={"X-Trace-Action": "1", "Origin": "https://attacker.example"},
            ).status_code
            == 403
        )
        app.config["IRIS_TRACE_TOKEN"] = "test-token"
        assert client.get("/debug/traces").status_code == 401
        assert (
            client.get(
                "/debug/traces", headers={"Authorization": "Bearer test-token"}
            ).status_code
            == 200
        )


def test_calibration_and_assertions_are_separate(app):
    trace = Trace(store_for(app), "/calibration", cache_bypass=True)
    token = CURRENT.set(trace)
    try:
        result = run_case(
            {
                "case_id": "bad-expectation",
                "mode": "layout",
                "input": {"regions": []},
                "assertions": [{"path": "text", "expected": "incorrect"}],
            }
        )
        assert result["calibration"]["result"] == "fail"
        trace.finish(result)
    finally:
        CURRENT.reset(token)
    assert snapshot(app, trace.id)["status"] == "completed"


def test_async_calibration_job_is_visible(app):
    with app.test_client() as client:
        response = client.post(
            "/debug/calibration/runs",
            json={
                "case_id": "empty-layout",
                "mode": "layout",
                "input": {"regions": []},
                "assertions": [],
            },
            headers={"X-Trace-Action": "1"},
        )
    assert response.status_code == 202
    until = time.time() + 3
    while time.time() < until:
        row = snapshot(app, response.json["trace_id"])
        if row and row["status"] != "running":
            break
        time.sleep(0.01)
    assert row["status"] == "completed"
    assert any(e["kind"] == "calibration.result" for e in row["events"])


def test_retention_does_not_delete_active_requests(app):
    s = store_for(app)
    s.max_traces = 1
    active = Trace(s, "/verify", {"text": "active"})
    old = Trace(s, "/verify", {"text": "old"})
    old.finish()
    latest = Trace(s, "/verify", {"text": "latest"})
    latest.finish()
    s.flush()
    with s.connect() as db:
        s._prune(db)
    assert s.get(active.id) is not None
    assert s.get(old.id) is None
    active.finish()


def test_invalid_or_ambiguous_stop_is_rejected():
    with pytest.raises(ValueError):
        validate_case(
            {
                "case_id": "x",
                "mode": "text",
                "allow_live": True,
                "input": {"text": "claim"},
                "stop_after": "claim.semantic",
            }
        )


def test_scoped_stop_only_stops_selected_claim(app):
    calls = []

    @traced("claim.semantic")
    def semantic():
        calls.append("semantic")
        return {"score": 0.5}

    @traced("claim.process")
    def process(claim):
        return semantic()

    trace = Trace(store_for(app), "/calibration", stop_after="claim.semantic")
    trace.stop_claim = "2"
    token = CURRENT.set(trace)
    try:
        assert process({"claim_id": "1"}) == {"score": 0.5}
        with pytest.raises(StopAfter):
            process({"claim_id": "2"})
        assert calls == ["semantic", "semantic"]
    finally:
        trace.finish()
        CURRENT.reset(token)


def test_skipped_scoped_target_does_not_continue_to_next_claim(app):
    @traced("claim.process")
    def process(claim):
        return {"cache_hit": True}

    trace = Trace(store_for(app), "/calibration", stop_after="claim.semantic")
    trace.stop_claim = "2"
    token = CURRENT.set(trace)
    try:
        with pytest.raises(TargetNotReached):
            process({"claim_id": "2"})
    finally:
        trace.finish()
        CURRENT.reset(token)
    assert snapshot(app, trace.id)["status"] == "target_not_reached"


def test_stop_configuration_does_not_hide_real_failure(app):
    trace = Trace(store_for(app), "/calibration", stop_after="image.ocr")
    trace.finish({"error": "failure"}, 500, ValueError())
    assert snapshot(app, trace.id)["status"] == "error"


def test_recorded_text_replay_uses_saved_dependencies(app):
    from test_week4_app import _fake_content_profile, _fake_search_result

    calls = []

    @traced("claims.extract", dependency=True)
    def extract(text, translated_text=None):
        calls.append("extract")
        return {
            "status": "ok",
            "claims": [{"claim_id": "1", "claim_text": text, "normalized_claim": text}],
            "contains_opinion": False,
            "contains_recommendation": False,
            "ignored_segments": [],
        }

    @traced("retrieval.fixture", dependency=True)
    def search(**kwargs):
        calls.append("search")
        return _fake_search_result()

    with patch.multiple(
        iris,
        detect_language=lambda t: "english",
        profile_content=lambda t, tr: _fake_content_profile(t, tr),
        extract_claims=extract,
        search_and_extract=search,
        get_cached_verdict=lambda *a: None,
        save_cached_verdict=lambda *a: None,
    ):
        with app.test_client() as client:
            source = client.post("/verify", json={"text": "DOH reports dengue cases."})
        source_id = source.headers["X-IRIS-Trace-ID"]
        snapshot(app, source_id)
        before = list(calls)
        trace = Trace(
            store_for(app), "/calibration", artifact_capture=True, cache_bypass=True
        )
        token = CURRENT.set(trace)
        try:
            result = run_case(
                {
                    "case_id": "replay",
                    "mode": "replay",
                    "source_trace": source_id,
                    "assertions": [
                        {"path": "verdict", "expected": source.json["verdict"]}
                    ],
                }
            )
            assert result["calibration"]["result"] == "pass"
            assert calls == before
            trace.finish(result)
        finally:
            CURRENT.reset(token)
        assert any(
            e["kind"] == "replay.used" for e in snapshot(app, trace.id)["events"]
        )


def test_redacted_recordings_are_not_claimed_replayable(app):
    trace = Trace(store_for(app), "/verify", artifact_capture=True)
    trace.artifact(
        "request_input", {"text": "Visit https://example.com/story?token=private"}
    )
    trace.finish()
    snapshot(app, trace.id)
    token = CURRENT.set(Trace(store_for(app), "/calibration/replay"))
    try:
        with pytest.raises(ValueError, match="complete recorded text input"):
            run_case(
                {"case_id": "redacted", "mode": "replay", "source_trace": trace.id}
            )
    finally:
        CURRENT.get().finish()
        CURRENT.reset(token)
