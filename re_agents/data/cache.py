"""Tiny SQLite cache so re-running a deal never pays for the same API call twice."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class ResponseCache:
    def __init__(self, path: Path, ttl_days: int = 30) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_days * 86400
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, saved REAL, body TEXT)"
        )

    @staticmethod
    def make_key(namespace: str, params: dict[str, Any]) -> str:
        blob = json.dumps(params, sort_keys=True, default=str)
        return f"{namespace}:{hashlib.sha256(blob.encode()).hexdigest()}"

    def get(self, key: str) -> Any | None:
        row = self.db.execute("SELECT saved, body FROM responses WHERE key = ?", (key,)).fetchone()
        if not row or time.time() - row[0] > self.ttl_seconds:
            return None
        return json.loads(row[1])

    def set(self, key: str, value: Any) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO responses (key, saved, body) VALUES (?, ?, ?)",
            (key, time.time(), json.dumps(value, default=str)),
        )
        self.db.commit()
