# IRIS TRACE

TRACE records requests processed by an explicitly enabled calibration backend and presents them in a local browser workspace. It uses the real verification pipeline; it does not change verification rules or final response bodies.

## Start

Use the same Python environment in which the IRIS backend dependencies are installed. From `iris-backend`:

```powershell
python run_trace.py --artifacts
```

Open **http://127.0.0.1:5000/debug/trace**. Send checks from the extension or Android to this backend as usual. Every `/verify` and `/verify-image` request received by this instance is traced, including invalid input and failures. Client debug mode is not required. Use `--port 5001` if port 5000 is already occupied, and point the clients at that port.

`--artifacts` explicitly saves controlled calibration inputs, images, OCR regions and dependency responses. It enables image overlays and recorded text replay. Omit it for bounded summary capture. Artifacts can contain submitted text and retrieved passages; use calibration data you intend to retain.

For Android on another device, set `IRIS_TRACE_TOKEN` to a strong value and use `python run_trace.py --host 0.0.0.0 --artifacts`. The viewer prompts for HTTP Basic authentication: username `trace`, password equal to the token. Use HTTPS through your deployment proxy before sending this credential over an untrusted network. The normal verification API retains its existing access behavior.

Alternatively, set `IRIS_TRACE_ENABLED=true` on your existing Flask launch. It is off by default. Use one TRACE writer service per application process; Flask must have capacity to answer viewer requests while verification is running. The supplied launcher is threaded and disables the development reloader/debugger.

## Workspace

- History lists recent requests, with search, status filters and pagination.
- Selecting a request opens a tab. Opening it again focuses the same tab; closing it does not delete the saved trace. Open IDs are restored within the browser session. Follow latest is optional.
- Claim scope selects the request overview or an individual claim, including multi-claim submissions.
- **Pipeline** contains nested operations with inputs, outputs, durations and returned domain outcomes. Expand a row to inspect it.
- **Claims** contains the original claim, normalized text, verdict and metadata. **Evidence** lists public sources.
- **Decisions** shows routing, verdict changes, final claim decisions and calibration assertion results.
- **Input and OCR** shows captured input, grouping/selection records, and retained/excluded boxes when image artifacts are available. Coordinates use the actual normalized OCR image dimensions.
- **Diagnostics** includes existing timing records, provider failures, configuration fingerprints and replay events.
- Compare two full trace IDs to inspect baseline/candidate stage-output differences. A difference is an observation, not automatically a failure.
- Export downloads the captured JSON record. Artifact references are included; exporting a summary is not a portable full replay bundle. Delete removes a completed trace and its artifacts. Active traces cannot be deleted.

Completed means execution finished. Domain failures such as `missing_dependency` are highlighted separately. Correctness appears as **Calibration: pass / fail / not_evaluated** only when labeled assertions were run. A client timeout does not necessarily mean the backend stopped. A request that never reaches Flask cannot appear in this backend history.

## Calibration cases

Expand **Run a calibration case** and submit a JSON case. The API allows two active calibration jobs per process. Supported modes:

| Mode | Input | Execution |
|---|---|---|
| `layout` | `regions` | Saved OCR regions, no recognition or network |
| `profile` | `text`, optional `translated_text` | Local profiler with AI disabled |
| `language` | `text` | Language detector |
| `attribution` | `claim` object, `source_text` | Attribution grounding |
| `keyword` | `claim` string, `articles` | Local keyword fallback |
| `component_validate` | `claim`, `components`, `assessments`, `articles` | Mechanical partition/citation validation |
| `semantic` | `claim`, `articles` | Semantic model; requires `allow_live: true` because model loading may download files |
| `component_review` | `claim`, `articles` | Configured AI reviewer; requires `allow_live: true` |
| `text` | `text` | Actual text pipeline; requires `allow_live: true` |
| `image` | `image_base64` | OCR followed by text pipeline; requires `allow_live: true` |
| `replay` | top-level `source_trace` | Recorded text input and dependency responses, no live fallback |

Example local case:

```json
{
  "case_id": "LAYOUT-001",
  "dataset_version": "my-cases-1",
  "label_version": "1",
  "mode": "layout",
  "input": {"regions": [{"text": "The claim is false", "bbox": [[0,0],[300,0],[300,40],[0,40]], "confidence": 0.98}]},
  "assertions": [{"path": "text", "op": "contains", "expected": "false"}]
}
```

Assertions use dotted object keys / list indexes, `equal`, `contains` or `approx`, an `expected` value and optional numeric `tolerance`. Missing fields fail the assertion. No assertions means not evaluated. The included starter cases are software fixtures, not a representative fact-checking benchmark or held-out evaluation set.

### Stop at a boundary

Add `stop_after`, for example `image.ocr`, `image.layout`, `text.language`, `text.translation`, `text.profile` or `claims.extract`. These run prerequisites and halt before downstream work.

For repeated claim boundaries, specify **both** `stop_after` and `claim_id`:

```json
{"case_id":"CLAIM-STOP-001","mode":"text","allow_live":true,"input":{"text":"Your multi-claim post"},"stop_after":"claim.semantic","claim_id":"2"}
```

Use the actual extracted claim ID shown in TRACE; it is not necessarily the displayed ordinal. Supported claim boundaries include cache read, retrieval, component preparation (the claim split, run while evidence is gathered), evidence gathering, political check, component review and complete claim processing. A claim's retrieval and preparation run before any claim is reviewed, because the claims of a post search together and share what they find. Calibration bypasses both cache reads and writes. Unknown claim IDs stop before shared retrieval. Bypassed targets return `target_not_reached`; actual errors remain errors.

Per-source and per-article parallel tasks are not cooperative stop boundaries because other work may already be dispatched. Inspect their spans and use saved component fixtures. A stop run is partial and is not a final fact-check verdict. Stop controls are only exposed through calibration, not ordinary client payloads.

### Recorded text replay

Record the original text request with artifact capture, then run:

```json
{"case_id":"REPLAY-001","mode":"replay","source_trace":"FULL_TRACE_ID","assertions":[{"path":"claim_count","expected":2}]}
```

Replay substitutes responses at instrumented dependency boundaries, keyed by captured input hashes. Missing or truncated recordings fail explicitly; live access is never substituted. Boundary outputs such as claim extraction or semantic scoring may themselves be recorded: replay is useful for orchestration and downstream behavior, but does not rerun the internals of a substituted component. To calibrate that component, run its isolated fixture or an explicitly live case. Image replay currently uses saved OCR-region fixtures; full image-request replay is not offered.

Changing prompts or source logic can invalidate a recording. Every run captures a source-file fingerprint (including uncommitted pipeline edits), model/threshold settings and optional dataset/label versions. Remote model internals and exact hardware determinism are not guaranteed. Artifact truncation is explicit; exported trace summaries alone are insufficient to reproduce a run.

The code commit, source fingerprint and installed dependency versions are snapshotted on first use in the process. Restart the calibration backend after editing code or configuration. Inputs or dependency results changed by redaction are marked non-replayable rather than presented as exact historical reproductions.

### Batch regression harness

```powershell
python -m iris_trace.calibration iris_trace/fixtures/starter.json --report .iris-trace/starter-report.json
```

The case file is a JSON array. Reports contain per-case trace IDs and assertion results; failed assertions or execution errors return a nonzero exit status. Keep calibration and held-out datasets separate. Compare runs against identical fixtures and inspect false-support failures separately from retrieval availability.

## Capture and storage

`IRIS_TRACE_PATH` defaults to `iris-backend/.iris-trace/traces.sqlite3`, separate from verdict caching. SQLite tables store the request index, incremental span/decision events and optional artifacts. A bounded writer queue (2,048 jobs and 32 MiB) keeps database writes off the verification thread. Queue/storage failures are exposed through viewer health, dropped-event counts and capture completeness; they must not change a returned verification result.

Default retention is seven days / 1,000 requests, with approximate logical budgets of 250 MiB for events and 500 MiB for artifacts. Cleanup runs at most every 30 seconds of writer activity, preserving active requests. Deleted SQLite pages are reused; the physical file does not necessarily shrink immediately. Individual event size is bounded to 64 KiB, per-request events to 1 MiB, previews to 2,000 characters and artifacts to 8 MiB. Truncation is marked. Old traces from owners whose heartbeat expired are marked incomplete after 120 seconds.

Secrets and credential-bearing URL components are redacted, binary inputs are omitted from summary JSON, and rendered text is escaped. These measures do not anonymize ordinary claim text. The viewer is loopback-only without a server token. IDs are correlation identifiers, not authorization. Same-origin headers are required for mutations. Browser storage contains only view IDs/preferences. Rich capture stays disabled when `IRIS_TRACE_ENABLED` is not set, regardless of a client's `debug` flag.

## Verification

Backend tests use Flask/requests/BeautifulSoup plus pytest and NumPy/Pillow for the existing fixtures. Heavy models and live provider calls are not needed for TRACE's automated tests:

```powershell
python -m pytest tests -q
python tests/test_week4_app.py
python tests/test_ocr_module.py
```

The browser test uses the extension's Playwright development dependency and installed Google Chrome. It launches an isolated fixture server and never tests against an existing backend:

```powershell
node tests/test_trace_ui.cjs
```

Set `IRIS_TEST_PYTHON` if the test backend needs a specific interpreter, and `IRIS_PLAYWRIGHT_PATH` if Playwright is installed outside `iris-extension/node_modules`. Optional `IRIS_TRACE_UI_OUTPUT` saves screenshots. Validate disabled/enabled performance with your full model environment and representative requests before assigning production overhead targets; this implementation does not claim zero overhead or verified fact-check accuracy.

In the reviewed working tree, two older standalone checks already fail without TRACE: `test_week4_app.py` expects HTTP 200 for an attributed claim while its component reviewer is unavailable, and `test_week4_helpers.py` expects an older attribution string. These same failures were reproduced against the saved pre-TRACE source. They are distinct from the TRACE tests and were not hidden by changing verification behavior.
