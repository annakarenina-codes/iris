"""Run the ten saved inputs unchanged through TRACE's live calibration path."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "iris-backend"
OUT = HERE / "retest-20260912"
OUT.mkdir(exist_ok=True)
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv

load_dotenv(BACKEND / ".env")
from iris_trace.core import Store, Trace, CURRENT
from iris_trace.calibration import run_case
from iris_trace.web import configuration

records = json.loads((HERE / "observed_trace_records.json").read_text(encoding="utf-8"))
store = Store(OUT / "traces.sqlite3")
manifest = {
    "started_utc": datetime.now(timezone.utc).isoformat(),
    "configuration": configuration(),
    "cache_policy": "bypass reads and writes (TRACE calibration)",
    "reference_status": "AI-assisted provisional, not human-approved",
    "backend_modified_by_this_run": False,
}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
summaries = []
try:
    for record in records:
        number = record["case"]
        case = {
            "case_id": f"SOLO-P{number:02d}",
            "dataset_version": "trace-ten-original-inputs-v1",
            "label_version": "solo-0.2-provisional",
            "mode": "text",
            "allow_live": True,
            "input": {"text": record["input"]["text"]},
        }
        trace = Trace(store, "/calibration/text", {**case["input"], "platform": "harness"}, True, True)
        token = CURRENT.set(trace)
        trace.artifact("request_input", case["input"])
        started = datetime.now(timezone.utc)
        print(f"START case {number} trace {trace.id}", flush=True)
        result = None
        error = None
        try:
            result = run_case(case)
            trace.finish(result)
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            trace.finish({"error": error}, 500, exc)
        finally:
            CURRENT.reset(token)
        store.flush()
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        output = {"case": number, "trace_id": trace.id, "original_trace_id": record["trace"]["id"], "started_utc": started.isoformat(), "elapsed_seconds": elapsed, "input": case["input"], "output": result, "error": error}
        (OUT / f"case-{number:02d}.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        summaries.append({k: v for k, v in output.items() if k not in {"input", "output"}})
        (OUT / "run-summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
        print(f"END case {number}: {'ERROR ' + error['type'] if error else 'completed'} ({elapsed:.1f}s)", flush=True)
finally:
    store.flush()
    store.close()
