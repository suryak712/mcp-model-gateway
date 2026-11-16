"""Append-only audit log: who called which tool, with which model, and what happened.
Prompts and outputs are NOT logged, only their sizes, so the log is safe to share with reviewers."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class AuditLog:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()

    def record(self, **event) -> None:
        event = {"ts": round(time.time(), 3), **event}
        line = json.dumps(event, sort_keys=True)
        with self._lock, self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
