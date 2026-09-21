"""Explicit fixture execution and dependency-recorded text replay."""

import json
import math
from .core import CURRENT, event, ReplayMissing, TargetNotReached, safe

MODES = {
    "layout",
    "profile",
    "language",
    "attribution",
    "keyword",
    "component_validate",
    "semantic",
    "component_review",
    "text",
    "image",
    "replay",
}
TARGETS = {
    "image.ocr",
    "image.layout",
    "text.language",
    "text.translation",
    "text.profile",
    "claims.extract",
    "claims.attribution",
    "claims.quote_mark",
    "claim.cache_read",
    "claim.retrieve",
    "claim.component_prepare",
    "claim.gather",
    "claim.political",
    "claim.component_review",
    "claim.process",
    "request.assemble",
}


def validate_case(case):
    if not isinstance(case, dict):
        raise ValueError("A case must be a JSON object.")
    if len(json.dumps(case)) > 12 * 1024 * 1024:
        raise ValueError("Case is too large.")
    if case.get("mode") not in MODES:
        raise ValueError("Unsupported calibration mode. See iris_trace/README.md.")
    if not isinstance(case.get("case_id"), str) or not 1 <= len(case["case_id"]) <= 100:
        raise ValueError("Provide a case_id of 1–100 characters.")
    if case.get("stop_after") and case["stop_after"] not in TARGETS:
        raise ValueError("Unsupported cooperative stop boundary.")
    if case.get("stop_after", "").startswith("claim.") and case.get("claim_id") is None:
        raise ValueError("Repeated claim stages require claim_id.")
    if (
        case["mode"] in {"text", "image", "semantic", "component_review"}
        and case.get("allow_live") is not True
    ):
        raise ValueError(
            "This mode requires allow_live: true. It may call configured providers or load a model."
        )
    data = case.get("input", {})
    if not isinstance(data, dict):
        raise ValueError("input must be an object.")
    if case["mode"] in {"profile", "language", "text"} and (
        not isinstance(data.get("text"), str)
        or not data["text"].strip()
        or len(data["text"]) > 60000
    ):
        raise ValueError("Provide nonempty input.text up to 60,000 characters.")
    if case["mode"] == "layout":
        regions = data.get("regions")
        if not isinstance(regions, list) or len(regions) > 100:
            raise ValueError("Provide up to 100 input.regions.")
        for r in regions:
            if not isinstance(r, dict) or not isinstance(r.get("text"), str):
                raise ValueError("Each region needs text.")
            box = r.get("bbox", [])
            if box and (
                len(box) != 4
                or any(
                    not isinstance(p, list)
                    or len(p) != 2
                    or any(
                        not isinstance(x, (int, float)) or not math.isfinite(x)
                        for x in p
                    )
                    for p in box
                )
            ):
                raise ValueError("bbox must contain four finite coordinate pairs.")
    if case["mode"] == "replay" and (
        not isinstance(case.get("source_trace"), str) or len(case["source_trace"]) != 32
    ):
        raise ValueError("Provide source_trace for recorded text replay.")
    assertions = case.get("assertions", [])
    if not isinstance(assertions, list) or len(assertions) > 100:
        raise ValueError("Provide up to 100 assertions.")
    for a in assertions:
        if (
            not isinstance(a, dict)
            or not isinstance(a.get("path"), str)
            or a.get("op", "equal") not in {"equal", "contains", "approx"}
            or "expected" not in a
        ):
            raise ValueError(
                "Each assertion needs path, expected and op: equal, contains or approx."
            )


def compare(output, assertions):
    results = []
    for assertion in assertions:
        actual = output
        error = None
        try:
            for segment in assertion["path"].split("."):
                actual = (
                    actual[int(segment)]
                    if isinstance(actual, (list, tuple))
                    else actual[segment]
                )
            op = assertion.get("op", "equal")
            expected = assertion["expected"]
            passed = (
                (actual == expected)
                if op == "equal"
                else (expected in actual)
                if op == "contains"
                else abs(float(actual) - float(expected))
                <= float(assertion.get("tolerance", 0.001))
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            passed = False
            error = type(exc).__name__
        results.append(
            {
                **assertion,
                "actual": actual,
                "result": "pass" if passed else "fail",
                "error": error,
            }
        )
    return {
        "result": "not_evaluated"
        if not results
        else "pass"
        if all(r["result"] == "pass" for r in results)
        else "fail",
        "assertions": results,
    }


def run_case(case):
    validate_case(case)
    trace = CURRENT.get()
    mode = case["mode"]
    data = case.get("input", {})
    from .web import configuration

    event(
        "calibration.manifest",
        case_id=case["case_id"],
        mode=mode,
        cache_policy="bypass",
        dataset_version=case.get("dataset_version"),
        label_version=case.get("label_version"),
        configuration=configuration(),
    )
    if mode == "layout":
        from pipeline.ocr_layout import select_content_regions

        selected, excluded = select_content_regions(data["regions"])
        output = {
            "regions": selected,
            "excluded": excluded,
            "text": " ".join(r["text"] for r in selected),
        }
        event(
            "ocr.selection",
            raw_regions=data["regions"],
            retained=selected,
            excluded=excluded,
        )
    elif mode == "profile":
        from pipeline.content_profiler import profile_content

        output = profile_content(
            data["text"], data.get("translated_text"), use_ai=False
        )
    elif mode == "language":
        from pipeline.language_detector import detect_language

        output = {"language": detect_language(data["text"])}
    elif mode == "attribution":
        from pipeline.attribution_integrity import ground_attribution

        output = ground_attribution(data.get("claim", {}), data.get("source_text", ""))
    elif mode == "keyword":
        from pipeline.keyword_fallback import keyword_overlap_verdict

        output = keyword_overlap_verdict(
            data.get("claim", ""), data.get("articles", [])
        )
    elif mode == "component_validate":
        from pipeline.component_evidence import validate_review

        output = validate_review(
            data.get("claim", ""),
            data.get("components", []),
            data.get("assessments", []),
            data.get("articles", []),
        )
    elif mode == "semantic":
        from pipeline.verdict_generator import generate_verdict

        output = generate_verdict(data.get("claim", ""), data.get("articles", []))
    elif mode == "component_review":
        from pipeline.component_evidence import review_components

        output = review_components(data.get("claim", ""), data.get("articles", []))
    elif mode == "image":
        from pipeline.ocr import decode_base64_image, extract_text_from_image
        from app import verify_text_payload

        decoded = decode_base64_image(data.get("image_base64", ""))
        if decoded.get("status") != "ok":
            raise ValueError(decoded.get("message", "Invalid image"))
        ocr = extract_text_from_image(decoded["image_bytes"])
        output = verify_text_payload(ocr["text"]) if ocr.get("status") == "ok" else ocr
    else:
        from app import verify_text_payload

        if mode == "replay":
            if trace is None:
                raise ValueError("Recorded replay needs a TRACE context.")
            with trace.store.connect() as db:
                source = db.execute(
                    "SELECT input_type FROM traces WHERE id=?", (case["source_trace"],)
                ).fetchone()
                if source is None:
                    raise ValueError("Source trace not found or expired.")
                rows = db.execute(
                    "SELECT kind,data FROM artifacts WHERE trace_id=?",
                    (case["source_trace"],),
                ).fetchall()
            inputs = [
                json.loads(r["data"]) for r in rows if r["kind"] == "request_input"
            ]
            if (
                not inputs
                or not isinstance(inputs[0].get("text"), str)
                or not inputs[0].get("_trace_complete")
            ):
                raise ValueError(
                    "Replay requires a complete recorded text input. Enable artifact capture for the original request."
                )
            data = inputs[0]
            trace.replay = {}
            for row in rows:
                if row["kind"] != "dependency":
                    continue
                recording = json.loads(row["data"])
                if not recording.get("complete"):
                    continue
                key = (recording["stage_id"], recording["input_sha256"])
                trace.replay.setdefault(key, []).append(recording["output"])
            if not trace.replay:
                raise ValueError("No complete dependency recordings are available.")
            event("replay.source", trace_id=case["source_trace"])
        output = verify_text_payload(data["text"])
        if trace is not None and trace.replay_missing:
            raise ReplayMissing(
                "Replay is incomplete; no live dependency calls were allowed."
            )
    if trace and trace.stop_after and not trace.target_reached:
        raise TargetNotReached(
            trace.stop_after, "The pipeline exited before the target stage."
        )
    evaluation = compare(output, case.get("assertions", []))
    event("calibration.result", **evaluation)
    if trace:
        trace.artifact("calibration_output", output)
    return (
        {**output, "calibration": evaluation}
        if isinstance(output, dict)
        else {"output": output, "calibration": evaluation}
    )


def main():
    import argparse
    from pathlib import Path
    from .core import Store, Trace, StopAfter

    parser = argparse.ArgumentParser(description="Run versioned TRACE fixture cases.")
    parser.add_argument("cases", type=Path, help="JSON array of cases")
    parser.add_argument(
        "--database", type=Path, default=Path(".iris-trace/traces.sqlite3")
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        parser.error("Cases must be a JSON array.")
    for case in cases:
        validate_case(case)
    store = Store(args.database)
    report = []
    try:
        for case in cases:
            trace = Trace(
                store,
                "/calibration/" + case["mode"],
                {"text": case["case_id"], "platform": "harness"},
                True,
                True,
                case.get("stop_after"),
            )
            trace.stop_claim = (
                str(case["claim_id"]) if case.get("claim_id") is not None else None
            )
            token = CURRENT.set(trace)
            try:
                result = run_case(case)
                trace.finish(result)
                report.append(
                    {
                        "case_id": case["case_id"],
                        "trace_id": trace.id,
                        **result.get("calibration", {}),
                    }
                )
            except StopAfter as stop:
                trace.finish({"stage": stop.stage, "output": safe(stop.result)})
                report.append(
                    {
                        "case_id": case["case_id"],
                        "trace_id": trace.id,
                        "result": "not_evaluated",
                        "stopped_after": stop.stage,
                    }
                )
            except TargetNotReached as stop:
                trace.finish({"status": "target_not_reached", "reason": stop.reason})
                report.append(
                    {
                        "case_id": case["case_id"],
                        "trace_id": trace.id,
                        "result": "not_evaluated",
                        "reason": stop.reason,
                    }
                )
            except Exception as exc:
                trace.finish({"error": str(exc)}, 500, exc)
                report.append(
                    {
                        "case_id": case["case_id"],
                        "trace_id": trace.id,
                        "result": "error",
                        "error": str(exc),
                    }
                )
            finally:
                CURRENT.reset(token)
    finally:
        store.flush()
        store.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cases": len(report),
                "failed": sum(r.get("result") in {"fail", "error"} for r in report),
                "report": str(args.report),
            }
        )
    )
    raise SystemExit(
        1 if any(r.get("result") in {"fail", "error"} for r in report) else 0
    )


if __name__ == "__main__":
    main()
