"""Bounded, fail-open capture. No Flask or ML dependencies in pipeline hooks."""

from __future__ import annotations

import contextvars
import functools
import hashlib
import inspect
import itertools
import json
import math
import queue
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from contextlib import contextmanager

CURRENT = contextvars.ContextVar("iris_trace", default=None)
PARENT = contextvars.ContextVar("iris_trace_parent", default=None)
CLAIM = contextvars.ContextVar("iris_trace_claim", default=None)
SECRET = re.compile(r"authorization|cookie|password|secret|token|api.?key", re.I)
URL = re.compile(r'https?://[^\s<>"\']+')


def clean_string(value):
    from urllib.parse import urlsplit, urlunsplit

    def clean_url(match):
        try:
            u = urlsplit(match.group())
            return urlunsplit((u.scheme, u.netloc.rsplit("@", 1)[-1], u.path, "", ""))
        except ValueError:
            return "[redacted URL]"

    value = URL.sub(clean_url, value)
    value = re.sub(
        r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+",
        r"\1=[redacted]",
        value,
    )
    return re.sub(r"(?i)(bearer\s+|sk-)[a-z0-9_\-]+", "[redacted]", value)


def safe(value, depth=0, limit=2000):
    """Snapshot JSON values without repr(), arbitrary iteration or large buffers."""
    if depth > 12:
        return {"truncated": True, "reason": "depth"}
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        text = clean_string(value)
        return (
            text
            if len(text) <= limit
            else {"preview": text[:limit], "length": len(text), "truncated": True}
        )
    if isinstance(value, bytes):
        return {
            "type": "bytes",
            "size": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    if isinstance(value, dict):
        result = {}
        for key, item in itertools.islice(value.items(), 100):
            key = str(key)
            if SECRET.search(key):
                result[key] = "[redacted]"
            elif key in {"image_base64", "image_data_url", "image_bytes"}:
                result[key] = {
                    "omitted": True,
                    "size": len(item) if isinstance(item, (str, bytes)) else None,
                }
            else:
                result[key] = safe(item, depth + 1, limit)
                if isinstance(item, str) and clean_string(item) != item:
                    result.setdefault("_redacted_fields", []).append(key)
        if len(value) > 100:
            result["_truncated_keys"] = len(value) - 100
        return result
    if isinstance(value, (list, tuple)):
        result = [safe(v, depth + 1, limit) for v in value[:100]]
        if len(value) > 100:
            result.append({"truncated_items": len(value) - 100})
        return result
    # NumPy scalar coordinates are common; never stringify an entire array/model.
    if type(value).__module__.startswith("numpy") and getattr(value, "ndim", -1) == 0:
        return safe(value.item(), depth + 1, limit)
    return {"type": type(value).__name__, "omitted": True}


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def redacted(value, depth=0):
    if depth > 12:
        return True
    if isinstance(value, str):
        return "[redacted" in value or clean_string(value) != value
    if isinstance(value, dict):
        return any(
            SECRET.search(str(k)) or redacted(v, depth + 1)
            for k, v in itertools.islice(value.items(), 100)
        )
    if isinstance(value, (list, tuple)):
        return any(redacted(v, depth + 1) for v in value[:100])
    return False


class Store:
    """One bounded writer per process. The web reader never shares a connection."""

    def __init__(self, path, max_traces=1000, days=7, max_bytes=250 * 1024 * 1024):
        self.path = str(path)
        self.max_traces, self.days, self.max_bytes = max_traces, days, max_bytes
        self.owner = uuid.uuid4().hex
        self.jobs = queue.Queue(maxsize=2048)
        self.queue_lock = threading.Lock()
        self.queued_bytes = 0
        self.error = None
        self.dropped = 0
        self._closed = False
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS owners(id TEXT PRIMARY KEY, heartbeat REAL);
                CREATE TABLE IF NOT EXISTS traces(
                    id TEXT PRIMARY KEY, owner TEXT, created REAL, ended REAL,
                    status TEXT, platform TEXT, input_type TEXT, title TEXT,
                    claim_count INTEGER DEFAULT 0, http_status INTEGER,
                    capture_status TEXT DEFAULT 'complete', summary TEXT);
                CREATE INDEX IF NOT EXISTS traces_created ON traces(created DESC);
                CREATE TABLE IF NOT EXISTS events(
                    trace_id TEXT REFERENCES traces(id) ON DELETE CASCADE,
                    seq INTEGER, data TEXT, PRIMARY KEY(trace_id,seq));
                CREATE TABLE IF NOT EXISTS artifacts(
                    id TEXT PRIMARY KEY, trace_id TEXT REFERENCES traces(id) ON DELETE CASCADE,
                    kind TEXT, mime TEXT, sha256 TEXT, data BLOB);
            """)
            db.execute(
                "UPDATE traces SET status='incomplete',capture_status='partial' WHERE status='running' AND owner IN (SELECT id FROM owners WHERE heartbeat<?)",
                (time.time() - 120,),
            )
            db.execute("INSERT INTO owners VALUES(?,?)", (self.owner, time.time()))
        self.worker = threading.Thread(
            target=self._write, name="iris-trace-writer", daemon=True
        )
        self.worker.start()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=0.25)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def submit(self, operation, args):
        weight = sum(
            len(x.encode("utf-8"))
            if isinstance(x, str)
            else len(x)
            if isinstance(x, bytes)
            else 16
            for x in args
        )
        try:
            with self.queue_lock:
                if self.queued_bytes + weight > 32 * 1024 * 1024:
                    raise queue.Full
                self.jobs.put_nowait((operation, args, weight))
                self.queued_bytes += weight
            return True
        except queue.Full:
            self.dropped += 1
            self.error = "Trace writer queue is full; capture is incomplete."
            return False

    def _write(self):
        last_cleanup = 0
        last_heartbeat = 0
        while not self._closed or not self.jobs.empty():
            try:
                operation, args, weight = self.jobs.get(timeout=0.5)
            except queue.Empty:
                if time.time() - last_heartbeat < 15:
                    continue
                operation, args, weight = "heartbeat", (), 0
            try:
                with self.connect() as db:
                    if operation == "start":
                        db.execute(
                            "INSERT INTO traces(id,owner,created,status,platform,input_type,title,summary) VALUES(?,?,?,?,?,?,?,?)",
                            args,
                        )
                    elif operation == "event":
                        db.execute("INSERT INTO events VALUES(?,?,?)", args)
                    elif operation == "finish":
                        db.execute(
                            "UPDATE traces SET ended=?,status=?,http_status=?,claim_count=?,capture_status=?,summary=? WHERE id=?",
                            args,
                        )
                    elif operation == "metadata":
                        db.execute(
                            "UPDATE traces SET title=?,platform=? WHERE id=?", args
                        )
                    elif operation == "artifact":
                        db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?)", args)
                    db.execute(
                        "UPDATE owners SET heartbeat=? WHERE id=?",
                        (time.time(), self.owner),
                    )
                    last_heartbeat = time.time()
                    if time.time() - last_cleanup > 30:
                        self._prune(db)
                        last_cleanup = time.time()
            except Exception as exc:
                self.error = f"Trace storage unavailable ({type(exc).__name__}); capture may be incomplete."
                self.dropped += 1
            finally:
                if operation != "heartbeat":
                    with self.queue_lock:
                        self.queued_bytes -= weight
                    self.jobs.task_done()

    def _prune(self, db):
        db.execute(
            "UPDATE traces SET status='incomplete',capture_status='partial' WHERE status='running' AND owner IN (SELECT id FROM owners WHERE heartbeat<?)",
            (time.time() - 120,),
        )
        db.execute(
            "DELETE FROM traces WHERE status!='running' AND created<?",
            (time.time() - 86400 * self.days,),
        )
        db.execute(
            "DELETE FROM traces WHERE status!='running' AND id IN (SELECT id FROM traces ORDER BY created DESC LIMIT -1 OFFSET ?)",
            (self.max_traces,),
        )
        size = db.execute(
            "SELECT COALESCE(SUM(length(data)),0) FROM events"
        ).fetchone()[0]
        artifact_size = db.execute(
            "SELECT COALESCE(SUM(length(data)),0) FROM artifacts"
        ).fetchone()[0]
        while size > self.max_bytes or artifact_size > 500 * 1024 * 1024:
            row = db.execute(
                "SELECT id FROM traces WHERE status!='running' ORDER BY created LIMIT 1"
            ).fetchone()
            if not row:
                break
            db.execute("DELETE FROM traces WHERE id=?", (row[0],))
            size = db.execute(
                "SELECT COALESCE(SUM(length(data)),0) FROM events"
            ).fetchone()[0]
            artifact_size = db.execute(
                "SELECT COALESCE(SUM(length(data)),0) FROM artifacts"
            ).fetchone()[0]

    def flush(self, timeout=2):
        until = time.monotonic() + timeout
        while self.jobs.unfinished_tasks and time.monotonic() < until:
            time.sleep(0.005)
        return not self.jobs.unfinished_tasks

    def close(self):
        self._closed = True
        try:
            self.jobs.put_nowait(("shutdown", (), 0))
        except queue.Full:
            pass
        self.worker.join(timeout=3)

    def list(self, query="", status="", offset=0, limit=40):
        with self.connect() as db:
            where = "WHERE (title LIKE ? OR id LIKE ? OR platform LIKE ?) AND (?='' OR status=?)"
            args = ("%" + query + "%",) * 3 + (status, status)
            total = db.execute("SELECT count(*) FROM traces " + where, args).fetchone()[
                0
            ]
            rows = db.execute(
                "SELECT * FROM traces "
                + where
                + " ORDER BY created DESC LIMIT ? OFFSET ?",
                args + (limit, offset),
            ).fetchall()
        return {"items": [self._row(r) for r in rows], "total": total, "offset": offset}

    @staticmethod
    def _row(row):
        result = dict(row)
        result["summary"] = json.loads(result["summary"] or "{}")
        return result

    def get(self, trace_id, after=0):
        with self.connect() as db:
            row = db.execute("SELECT * FROM traces WHERE id=?", (trace_id,)).fetchone()
            if not row:
                return None
            result = self._row(row)
            result["events"] = [
                json.loads(e[0])
                for e in db.execute(
                    "SELECT data FROM events WHERE trace_id=? AND seq>? ORDER BY seq",
                    (trace_id, after),
                )
            ]
            result["artifacts"] = [
                dict(a)
                for a in db.execute(
                    "SELECT id,kind,mime,sha256,length(data) AS size FROM artifacts WHERE trace_id=?",
                    (trace_id,),
                )
            ]
            result["revision"] = db.execute(
                "SELECT COALESCE(MAX(seq),0) FROM events WHERE trace_id=?", (trace_id,)
            ).fetchone()[0]
            return result


class Trace:
    def __init__(
        self,
        store,
        endpoint,
        payload=None,
        artifact_capture=False,
        cache_bypass=False,
        stop_after=None,
    ):
        self.store, self.id = store, uuid.uuid4().hex
        self.started, self.created = time.perf_counter(), time.time()
        self.lock = threading.RLock()
        self.seq = self.size = 0
        self.partial = False
        self.finished = False
        self.spans = {}
        self.artifact_capture = artifact_capture
        self.cache_bypass = cache_bypass
        self.stop_after = stop_after
        self.stop_claim = None
        self.target_reached = False
        self.replay = None
        self.replay_missing = False
        self.artifact_ids = {}
        payload = payload if isinstance(payload, dict) else {}
        self.input_type = (
            "image"
            if endpoint.endswith("image")
            else "fixture"
            if endpoint.startswith("/calibration")
            and not endpoint.endswith(("text", "replay"))
            else "text"
        )
        title = payload.get("text") or (
            "Image request" if self.input_type == "image" else "Text request"
        )
        title = (
            clean_string(title)[:90]
            if isinstance(title, str)
            else "Invalid text request"
        )
        platform = payload.get("platform", "unknown")
        if platform not in {"android", "chrome", "harness"}:
            platform = "unknown"
        self.store.submit(
            "start",
            (
                self.id,
                store.owner,
                self.created,
                "running",
                platform,
                self.input_type,
                title,
                encode(
                    {"endpoint": endpoint, "schema_version": 2, "registry_version": 2}
                ),
            ),
        )
        self.emit("request.input", data=payload)

    def emit(self, kind, **values):
        try:
            with self.lock:
                data = safe(values)
                self.seq += 1
                event = dict(
                    data,
                    kind=kind,
                    seq=self.seq,
                    trace_id=self.id,
                    offset_ms=round((time.perf_counter() - self.started) * 1000, 2),
                )
                event.setdefault("parent_span_id", PARENT.get())
                event.setdefault("claim_id", CLAIM.get())
                raw = encode(event)
                if len(raw.encode("utf-8")) > 64000:
                    event["data"] = {"truncated": True, "reason": "event_size"}
                    event.pop("input", None)
                    event.pop("output", None)
                    raw = encode(event)
                    self.partial = True
                if self.size + len(raw.encode("utf-8")) > 1024 * 1024:
                    self.partial = True
                    return
                self.size += len(raw.encode("utf-8"))
                if not self.store.submit("event", (self.id, self.seq, raw)):
                    self.partial = True
        except Exception:
            self.partial = True

    def artifact(self, kind, data, mime="application/json"):
        if not self.artifact_capture:
            return None
        try:
            if kind == "request_input" and isinstance(data, dict):
                data = {
                    **data,
                    "_trace_complete": not has_loss(safe(data, limit=60000))
                    and not redacted(data),
                }
            raw = (
                data
                if isinstance(data, bytes)
                else encode(safe(data, limit=60000)).encode("utf-8")
            )
            if len(raw) > 8 * 1024 * 1024:
                self.emit(
                    "capture.warning", data={"reason": "artifact_size", "kind": kind}
                )
                return None
            digest = hashlib.sha256(raw).hexdigest()
            if (kind, digest) in self.artifact_ids:
                return self.artifact_ids[(kind, digest)]
            artifact_id = uuid.uuid4().hex
            self.artifact_ids[(kind, digest)] = artifact_id
            if not self.store.submit(
                "artifact", (artifact_id, self.id, kind, mime, digest, raw)
            ):
                self.partial = True
                return None
            self.emit("artifact", data={"id": artifact_id, "kind": kind})
            return artifact_id
        except Exception:
            self.partial = True
            return None

    def finish(self, payload=None, http_status=200, error=None):
        if self.finished:
            return
        self.finished = True
        payload = payload if isinstance(payload, dict) else {}
        status = (
            "error"
            if error or http_status >= 500
            else "rejected"
            if http_status >= 400
            else "completed"
        )
        if self.stop_after and not error and http_status < 400:
            status = "partial" if self.target_reached else "target_not_reached"
        self.emit(
            "request.result",
            data=payload,
            http_status=http_status,
            error=type(error).__name__ if error else None,
        )
        self.store.submit(
            "finish",
            (
                time.time(),
                status,
                http_status,
                payload.get("claim_count", len(payload.get("claims") or [])),
                "partial" if self.partial or self.store.error else "complete",
                encode(
                    safe(
                        {
                            "verdict": payload.get("verdict"),
                            "message": payload.get("message"),
                            "calibration_result": payload.get("calibration", {}).get(
                                "result"
                            ),
                            "duration_ms": round(
                                (time.perf_counter() - self.started) * 1000, 2
                            ),
                            "stop_after": self.stop_after,
                            "target_reached": self.target_reached,
                        }
                    )
                ),
                self.id,
            ),
        )


class StopAfter(BaseException):
    """Internal cooperative control signal; provider fallback handlers must not swallow it."""

    def __init__(self, stage, result):
        self.stage, self.result = stage, result


class TargetNotReached(BaseException):
    def __init__(self, stage, reason):
        self.stage, self.reason = stage, reason


def outcome(result):
    if not isinstance(result, dict):
        return None
    return (
        result.get("status")
        or result.get("scoring_status")
        or ("cache_hit" if result.get("cache_hit") else None)
    )


@contextmanager
def span(stage, inputs=None):
    trace = CURRENT.get()
    if trace is None:
        yield None
        return
    ident = uuid.uuid4().hex
    parent = PARENT.get()
    trace.spans[ident] = stage
    trace.emit(
        "span.start", span_id=ident, stage_id=stage, parent_span_id=parent, input=inputs
    )
    token = PARENT.set(ident)
    started = time.perf_counter()
    state = {"output": None}
    try:
        yield state
    except BaseException as exc:
        import traceback

        try:
            detail = {
                "type": type(exc).__name__,
                "message": clean_string(str(exc))[:2000],
                "frames": [
                    {
                        "file": Path(f.filename).name,
                        "line": f.lineno,
                        "function": f.name,
                    }
                    for f in traceback.extract_tb(exc.__traceback__)[-8:]
                ],
            }
        except Exception:
            detail = {"type": type(exc).__name__}
        trace.emit(
            "span.end",
            span_id=ident,
            stage_id=stage,
            status="stopped"
            if isinstance(exc, (StopAfter, TargetNotReached))
            else "error",
            error=detail,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        raise
    else:
        result = state["output"]
        domain = outcome(result)
        trace.emit(
            "span.end",
            span_id=ident,
            stage_id=stage,
            status="completed",
            domain_outcome=domain,
            output=result,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    finally:
        PARENT.reset(token)


def input_key(inputs):
    return hashlib.sha256(
        json.dumps(
            safe(inputs, limit=60000), sort_keys=True, ensure_ascii=False
        ).encode()
    ).hexdigest()


def has_loss(value):
    if isinstance(value, dict):
        return any(
            k in value
            for k in ("truncated", "omitted", "_truncated_keys", "truncated_items")
        ) or any(has_loss(v) for v in value.values())
    if isinstance(value, list):
        return any(has_loss(v) for v in value)
    return False


class ReplayMissing(RuntimeError):
    pass


def traced(stage, dependency=False):
    def decorate(fn):
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            trace = CURRENT.get()
            if trace is None:
                return fn(*args, **kwargs)
            try:
                inputs = dict(signature.bind_partial(*args, **kwargs).arguments)
            except TypeError:
                inputs = {}
            claim = inputs.get("claim")
            claim_token = (
                CLAIM.set(str(claim.get("claim_id")))
                if isinstance(claim, dict) and "claim_id" in claim
                else None
            )
            try:
                with span(stage, inputs) as state:
                    key = input_key(inputs) if dependency else None
                    if dependency and trace.replay is not None:
                        records = trace.replay.get((stage, key), [])
                        if not records:
                            trace.replay_missing = True
                            raise ReplayMissing(
                                "No recorded response for "
                                + stage
                                + "; live access is disabled."
                            )
                        result = records.pop(0)
                        trace.emit(
                            "replay.used", data={"stage_id": stage, "input_sha256": key}
                        )
                    else:
                        result = fn(*args, **kwargs)
                    state["output"] = result
                    if (
                        stage == "image.acquire_decode"
                        and isinstance(result, dict)
                        and isinstance(result.get("image_bytes"), bytes)
                    ):
                        raw = result["image_bytes"]
                        mime = (
                            "image/png"
                            if raw.startswith(b"\x89PNG")
                            else "image/jpeg"
                            if raw.startswith(b"\xff\xd8")
                            else "image/webp"
                            if raw[:4] == b"RIFF"
                            else "application/octet-stream"
                        )
                        trace.artifact("image", raw, mime)
                    if dependency and trace.artifact_capture:
                        captured = safe(result, limit=60000)
                        trace.artifact(
                            "dependency",
                            {
                                "stage_id": stage,
                                "input_sha256": key,
                                "output": captured,
                                "complete": not has_loss(captured)
                                and not has_loss(safe(inputs, limit=60000))
                                and not redacted(inputs)
                                and not redacted(result),
                            },
                        )
                if trace.stop_after == stage and (
                    trace.stop_claim is None or trace.stop_claim == CLAIM.get()
                ):
                    trace.target_reached = True
                    raise StopAfter(stage, result)
                if (
                    stage == "claim.process"
                    and trace.stop_claim == CLAIM.get()
                    and trace.stop_after
                    and not trace.target_reached
                ):
                    raise TargetNotReached(
                        trace.stop_after, "The selected claim bypassed this stage."
                    )
                return result
            finally:
                if claim_token is not None:
                    CLAIM.reset(claim_token)

        return wrapped

    return decorate


def event(kind, **data):
    trace = CURRENT.get()
    if trace is not None:
        trace.emit(kind, data=data)


def submit_context(executor, fn, *args):
    if CURRENT.get() is None:
        return executor.submit(fn, *args)
    return executor.submit(contextvars.copy_context().run, fn, *args)
