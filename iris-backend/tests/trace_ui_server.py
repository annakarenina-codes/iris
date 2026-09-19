import sys
from pathlib import Path
from unittest.mock import patch
from io import BytesIO
import base64

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import app as iris
from test_week4_app import _fake_content_profile, _fake_search_result, _fake_verdict
from iris_trace.core import event, traced, CURRENT
from iris_trace.web import store_for
from PIL import Image
from werkzeug.serving import make_server

import argparse
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
args = parser.parse_args()
fixture_directory = tempfile.TemporaryDirectory(prefix="iris-trace-ui-")
iris.app.config.update(
    IRIS_TRACE_ENABLED=True,
    IRIS_TRACE_PATH=str(Path(fixture_directory.name) / "traces.sqlite3"),
    IRIS_TRACE_ARTIFACTS=True,
    IRIS_TRACE_TOKEN=None,
)
extract = lambda *args: {
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


@traced("image.ocr")
def ocr(_):
    regions = [
        {
            "text": "DOH reports dengue cases",
            "confidence": 0.98,
            "bbox": [[10, 20], [180, 20], [180, 50], [10, 50]],
        },
        {
            "text": "Publisher",
            "confidence": 0.7,
            "bbox": [[10, 160], [150, 160], [150, 180], [10, 180]],
        },
    ]
    event(
        "ocr.selection",
        raw_regions=regions,
        retained=regions[:1],
        excluded=[{"text": "Publisher", "reason": "secondary_block"}],
        image={
            "original_size": [400, 400],
            "preprocessing": {"normalized_size": [200, 200]},
        },
    )
    CURRENT.get().artifact("ocr_regions", regions)
    return {
        "status": "ok",
        "text": "DOH reports dengue cases",
        "confidence": 0.98,
        "word_count": 4,
        "low_confidence": False,
        "warnings": [],
        "regions": regions[:1],
    }


with patch.multiple(
    iris,
    detect_language=lambda t: "english",
    translate_to_english=lambda t, l: t,
    profile_content=lambda t, tr: _fake_content_profile(t, tr),
    extract_claims=extract,
    search_and_extract=lambda **kw: _fake_search_result(),
    generate_verdict=_fake_verdict,
    get_cached_verdict=lambda *a: None,
    save_cached_verdict=lambda *a: None,
    refine_with_openai_rag=lambda *a: {
        "status": "not_needed",
        "used": False,
        "result": None,
        "error": None,
    },
    extract_text_from_image=ocr,
):
    with iris.app.test_client() as client:
        client.post(
            "/verify",
            json={
                "text": '<img src=x onerror="window.BAD=true"> DOH reports dengue cases.',
                "platform": "chrome",
            },
        )
        buf = BytesIO()
        Image.new("RGB", (400, 400), "white").save(buf, format="PNG")
        client.post(
            "/verify-image",
            json={
                "image_base64": base64.b64encode(buf.getvalue()).decode(),
                "platform": "android",
            },
        )
        client.post("/verify", json={"text": ""})
store_for(iris.app).flush()
print("TRACE_UI_READY", flush=True)
server = make_server("127.0.0.1", args.port, iris.app, threaded=True)
try:
    server.serve_forever()
finally:
    server.server_close()
    store_for(iris.app).close()
    fixture_directory.cleanup()
