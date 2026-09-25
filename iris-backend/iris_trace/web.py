"""Developer-only viewer, lifecycle hooks and bounded calibration jobs."""

import hmac
import json
import os
import threading
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    g,
    got_request_exception,
    jsonify,
    render_template,
    request,
    send_file,
)

from .core import CURRENT, Store, Trace, StopAfter, TargetNotReached, safe, span

bp = Blueprint(
    "iris_trace",
    __name__,
    url_prefix="/debug",
    template_folder="templates",
    static_folder="static",
)
_stores_lock = threading.Lock()


def enabled(app):
    return bool(app.config.get("IRIS_TRACE_ENABLED"))


def store_for(app):
    with _stores_lock:
        store = app.extensions.get("iris_trace_store")
        path = app.config["IRIS_TRACE_PATH"]
        if store is None or store.path != str(path):
            store = Store(path)
            app.extensions["iris_trace_store"] = store
        return store


@bp.before_request
def authorize():
    if not enabled(current_app):
        abort(404)
    token = current_app.config.get("IRIS_TRACE_TOKEN")
    host = urlsplit(request.host_url).hostname
    local = request.remote_addr in {"127.0.0.1", "::1"} and host in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if token:
        auth = request.authorization
        offered = (
            auth.password
            if auth and auth.type == "basic"
            else request.headers.get("Authorization", "").removeprefix("Bearer ")
        )
        if not offered or not hmac.compare_digest(str(token), offered):
            return Response(
                "TRACE authentication required. Use username trace and your server token.",
                401,
                {"WWW-Authenticate": 'Basic realm="IRIS TRACE"'},
            )
    elif not local:
        abort(
            403,
            description="TRACE is local-only. Configure IRIS_TRACE_TOKEN before remote access.",
        )
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("Origin")
        if (
            origin and origin.rstrip("/") != request.host_url.rstrip("/")
        ) or request.headers.get("X-Trace-Action") != "1":
            abort(403, description="Same-origin TRACE action required.")


@bp.after_request
def protect(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' blob:; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@bp.get("/trace")
@bp.get("/trace/<trace_id>")
def viewer(trace_id=None):
    return render_template("trace.html")


@bp.get("/traces")
def index():
    try:
        offset = max(0, int(request.args.get("offset", 0)))
        result = store_for(current_app).list(
            request.args.get("q", "")[:200], request.args.get("status", ""), offset
        )
        result["health"] = {
            "error": store_for(current_app).error,
            "dropped_events": store_for(current_app).dropped,
        }
        return jsonify(result)
    except (ValueError, TypeError):
        abort(400)
    except Exception:
        return jsonify(error="Trace storage unavailable."), 503


@bp.get("/traces/<trace_id>")
@bp.get("/traces/<trace_id>/events")
def details(trace_id):
    try:
        after = max(0, int(request.args.get("after", 0)))
    except ValueError:
        abort(400)
    result = store_for(current_app).get(trace_id, after)
    if result is None:
        abort(404, description="Trace not found or expired.")
    return jsonify(result)


@bp.get("/traces/<trace_id>/export")
def export(trace_id):
    result = store_for(current_app).get(trace_id)
    if result is None:
        abort(404)
    return Response(
        json.dumps(result, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="trace-{result["id"]}.json"'
        },
    )


@bp.get("/artifacts/<artifact_id>")
def artifact(artifact_id):
    with store_for(current_app).connect() as db:
        row = db.execute(
            "SELECT * FROM artifacts WHERE id=?", (artifact_id,)
        ).fetchone()
    if row is None:
        abort(404)
    return send_file(
        BytesIO(row["data"]),
        mimetype=row["mime"],
        download_name="trace-artifact",
        max_age=0,
    )


@bp.delete("/traces/<trace_id>")
def delete(trace_id):
    store = store_for(current_app)
    with store.connect() as db:
        row = db.execute("SELECT status FROM traces WHERE id=?", (trace_id,)).fetchone()
        if row is None:
            abort(404)
        if row["status"] == "running":
            return jsonify(error="A running trace cannot be deleted."), 409
        db.execute("DELETE FROM traces WHERE id=?", (trace_id,))
    return jsonify(deleted=True)


@bp.post("/calibration/runs")
def calibration_run():
    from .calibration import validate_case, run_case

    data = request.get_json(silent=True)
    try:
        validate_case(data)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    app = current_app._get_current_object()
    slots = app.extensions["iris_trace_slots"]
    if not slots.acquire(blocking=False):
        return jsonify(error="Two calibration runs are already active."), 429
    try:
        trace = Trace(
            store_for(app),
            "/calibration/" + data["mode"],
            {"text": data.get("case_id", "Calibration case"), "platform": "harness"},
            artifact_capture=True,
            cache_bypass=True,
            stop_after=data.get("stop_after"),
        )
        trace.stop_claim = (
            str(data["claim_id"]) if data.get("claim_id") is not None else None
        )
        trace.emit("calibration.case", data=data)

        def work():
            token = CURRENT.set(trace)
            try:
                with app.app_context():
                    result = run_case(data)
                trace.finish(result)
            except StopAfter as stop:
                trace.finish(
                    {
                        "status": "stopped_after_target",
                        "stage": stop.stage,
                        "output": safe(stop.result),
                    }
                )
            except TargetNotReached as stop:
                trace.finish(
                    {
                        "status": "target_not_reached",
                        "stage": stop.stage,
                        "reason": stop.reason,
                    }
                )
            except Exception as exc:
                trace.finish(
                    {"error": type(exc).__name__, "message": str(exc)}, 500, exc
                )
            finally:
                CURRENT.reset(token)
                slots.release()

        threading.Thread(target=work, name="iris-calibration", daemon=True).start()
        return jsonify(trace_id=trace.id), 202
    except Exception:
        slots.release()
        raise


def init_app(app):
    app.config.setdefault(
        "IRIS_TRACE_ENABLED",
        os.getenv("IRIS_TRACE_ENABLED", "").lower() in {"true", "1", "yes"},
    )
    app.config.setdefault(
        "IRIS_TRACE_PATH",
        os.getenv(
            "IRIS_TRACE_PATH",
            str(Path(app.root_path) / ".iris-trace" / "traces.sqlite3"),
        ),
    )
    app.config.setdefault("IRIS_TRACE_TOKEN", os.getenv("IRIS_TRACE_TOKEN"))
    app.config.setdefault(
        "IRIS_TRACE_ARTIFACTS",
        os.getenv("IRIS_TRACE_ARTIFACTS", "").lower() in {"true", "1", "yes"},
    )
    app.extensions["iris_trace_slots"] = threading.BoundedSemaphore(2)
    app.register_blueprint(bp)

    @got_request_exception.connect_via(app)
    def capture_exception(sender, exception, **extra):
        trace = CURRENT.get()
        if trace:
            try:
                trace.emit(
                    "request.exception",
                    data={"type": type(exception).__name__, "message": str(exception)},
                )
            except Exception:
                trace.partial = True

    @app.before_request
    def begin():
        if not enabled(app) or request.path not in {"/verify", "/verify-image"}:
            return
        try:
            trace = Trace(
                store_for(app),
                request.path,
                artifact_capture=app.config["IRIS_TRACE_ARTIFACTS"],
            )
            g.iris_trace = trace
            g.iris_trace_token = CURRENT.set(trace)
            with span("request.parse_validate") as state:
                data = request.get_json(silent=True) if request.is_json else {}
                state["output"] = {
                    "json_object": isinstance(data, dict),
                    "content_type": request.mimetype,
                    "content_length": request.content_length,
                }
            if isinstance(data, dict):
                trace.emit("request.input", data=data)
                title = data.get("text")
                title = (
                    safe(title[:90])
                    if isinstance(title, str) and title.strip()
                    else (
                        "Image request"
                        if request.path.endswith("image")
                        else "Invalid or empty text request"
                    )
                )
                platform = data.get("platform", "unknown")
                if platform not in {"android", "chrome", "harness"}:
                    platform = "unknown"
                trace.store.submit("metadata", (title, platform, trace.id))
                trace.artifact("request_input", data)
            trace.emit("runtime.configuration", data=configuration(app))
        except Exception as exc:
            # Capture failures do not make valid client requests fail.
            app.logger.warning("TRACE capture could not start: %s", type(exc).__name__)

    @app.after_request
    def finish(response):
        trace = getattr(g, "iris_trace", None)
        if trace:
            try:
                trace.finish(response.get_json(silent=True), response.status_code)
                response.headers["X-IRIS-Trace-ID"] = trace.id
            except Exception:
                app.logger.warning("TRACE finalization failed.")
        return response

    @app.teardown_request
    def cleanup(error):
        trace = getattr(g, "iris_trace", None)
        if trace:
            try:
                if not trace.finished:
                    trace.finish({}, 500, error or RuntimeError())
            finally:
                token = getattr(g, "iris_trace_token", None)
                if token is not None:
                    CURRENT.reset(token)
                    g.iris_trace_token = None


@lru_cache(maxsize=2)
def configuration(app=None):
    """Snapshot once per process. Restart after code/configuration edits."""
    import hashlib
    import subprocess
    from importlib.metadata import version, PackageNotFoundError

    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(
        list((root / "pipeline").glob("*.py"))
        + list((root / "iris_trace").glob("*.py"))
        + [root / "app.py"]
    ):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    try:
        commit = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.strip()
            or None
        )
    except (OSError, subprocess.SubprocessError):
        commit = None
    dependencies = {}
    for name in ["Flask", "numpy", "easyocr", "sentence-transformers", "openai"]:
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = "not installed"
    from pipeline.verdict_generator import (
        MODEL_NAME,
        VERIFIED_THRESHOLD,
        PARTIAL_THRESHOLD,
    )

    return {
        "source_sha256": digest.hexdigest(),
        "code_commit": commit,
        "dependencies": dependencies,
        "snapshot_policy": "First use in this process; restart after edits",
        "semantic_model": MODEL_NAME,
        "verified_threshold": VERIFIED_THRESHOLD,
        "partial_threshold": PARTIAL_THRESHOLD,
        "settings": {
            key: os.getenv(key)
            for key in [
                "OPENAI_MODEL",
                "IRIS_OCR_GPU",
                "IRIS_SEARCH_WORKERS",
                "IRIS_ARTICLE_WORKERS",
                "IRIS_OCR_LOW_CONFIDENCE",
            ]
        },
    }
