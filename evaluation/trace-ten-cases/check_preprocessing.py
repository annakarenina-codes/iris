"""Live stage-only check; preserves the earlier full-verdict benchmark results."""

import json
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "iris-backend"
parser = argparse.ArgumentParser()
parser.add_argument('--output-name', default='preprocessing-fix')
args = parser.parse_args()
if Path(args.output_name).name != args.output_name:
    parser.error('output-name must be a single directory name')
OUT = HERE / args.output_name
OUT.mkdir(exist_ok=False)
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")
os.chdir(BACKEND)

from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")
from iris_trace.core import CURRENT, Store, Trace
from pipeline.language_detector import detect_language
from pipeline.translator import translate_to_english
from pipeline.content_profiler import profile_content

records = json.loads((HERE / "observed_trace_records.json").read_text(encoding="utf-8"))
store = Store(OUT / "traces.sqlite3")
summary = []
try:
    for record in records:
        number, original = record["case"], record["input"]["text"]
        trace = Trace(store, "/calibration/preprocessing", {"text": original, "platform": "harness"}, True, True)
        token = CURRENT.set(trace)
        output = {"case": number, "trace_id": trace.id,
                  "scope": "language, translation and profiling only; no final verdict test",
                  "started_utc": datetime.now(timezone.utc).isoformat(), "original_text": original}
        print(f"START case {number}", flush=True)
        try:
            language = detect_language(original)
            translated = translate_to_english(original, language)
            profile = profile_content(original, translated)
            output.update(language=language, translated_text=translated, profile=profile)
            trace.finish(output)
        except Exception as error:
            output["error"] = {"type": type(error).__name__, "message": str(error)}
            trace.finish(output, 500, error)
        finally:
            CURRENT.reset(token)
        store.flush()
        (OUT / f"case-{number:02d}.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        profile = output.get("profile", {})
        item = {"case": number, "trace_id": trace.id, "error": output.get("error"),
                "eligible": profile.get("eligible_for_verification"),
                "route": profile.get("recommended_route"),
                "ai_status": profile.get("openai_profile", {}).get("status"),
                "eligible_segments": sum(s["eligible_for_verification"] for s in profile.get("segments", []))}
        summary.append(item)
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(item), flush=True)
finally:
    store.flush()
    store.close()
