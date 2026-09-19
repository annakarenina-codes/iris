"""SQLite verdict cache for IRIS Week 4."""

from __future__ import annotations

from iris_trace.core import traced, event, CURRENT

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[1] / "iris_cache.sqlite3"


def get_cache_path() -> Path:
    return Path(os.getenv("IRIS_CACHE_PATH", str(DEFAULT_CACHE_PATH)))


def hash_claim(claim: str) -> str:
    normalized = " ".join(claim.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def init_cache(cache_path: Optional[Path] = None) -> None:
    path = cache_path or get_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS verdict_cache (
                claim_hash TEXT PRIMARY KEY,
                claim_text TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


@traced('claim.cache_read', dependency=False)
def get_cached_verdict(claim_hash: str, cache_path: Optional[Path] = None) -> Optional[Dict[str, object]]:
    trace = CURRENT.get()
    if trace is not None and trace.cache_bypass:
        event('cache.bypassed', reason='calibration')
        return None
    init_cache(cache_path)
    path = cache_path or get_cache_path()

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT result_json FROM verdict_cache WHERE claim_hash = ?",
            (claim_hash,),
        ).fetchone()

    if not row:
        return None

    return json.loads(row[0])


@traced('claim.cache_write', dependency=False)
def save_cached_verdict(
    claim_hash: str,
    claim_text: str,
    result: Dict[str, object],
    cache_path: Optional[Path] = None,
) -> None:
    trace = CURRENT.get()
    if trace is not None and trace.cache_bypass:
        event('cache.bypassed', reason='calibration')
        return None
    init_cache(cache_path)
    path = cache_path or get_cache_path()
    timestamp = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO verdict_cache (
                claim_hash,
                claim_text,
                result_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(claim_hash) DO UPDATE SET
                claim_text = excluded.claim_text,
                result_json = excluded.result_json,
                updated_at = excluded.updated_at
            """,
            (
                claim_hash,
                claim_text,
                json.dumps(result),
                timestamp,
                timestamp,
            ),
        )
