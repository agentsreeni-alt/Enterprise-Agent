"""Immutable audit log (control #5).

The orchestrator wraps every stage call with a start/end record automatically
-- stage authors never opt in or out. Each run gets its own append-only JSONL
file; no code path in this package rewrites or truncates it.

Durable storage: when `ENTERPRISE_AGENT_AUDIT_DB` is set, every record is
also (not instead) written to a SQLite database at that path -- durable,
queryable, and safe for concurrent runs (SQLite serializes writers), unlike
a bare JSONL file. The JSONL file always keeps being written regardless, so
existing consumers of it are unaffected.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_DB_ENV = "ENTERPRISE_AGENT_AUDIT_DB"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    stage TEXT NOT NULL,
    event TEXT NOT NULL,
    fields_json TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteAuditStore:
    """Durable, queryable audit storage. One process-wide connection per
    database path; SQLite serializes concurrent writers itself, so no
    additional locking is needed here.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def record(self, run_id: str, ts: str, stage: str, event: str, fields: dict) -> None:
        self._conn.execute(
            "INSERT INTO audit_log (run_id, ts, stage, event, fields_json) VALUES (?, ?, ?, ?, ?)",
            (run_id, ts, stage, event, json.dumps(fields)),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


@dataclass
class AuditLogger:
    run_dir: Path
    run_id: str = ""
    _sqlite_store: SqliteAuditStore | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = self.run_dir.name
        db_path = os.environ.get(AUDIT_DB_ENV)
        if db_path and self._sqlite_store is None:
            self._sqlite_store = SqliteAuditStore(Path(db_path))

    @property
    def log_path(self) -> Path:
        return self.run_dir / "audit.log"

    def record(self, stage: str, event: str, **fields: Any) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        ts = _now_iso()
        entry = {"ts": ts, "stage": stage, "event": event, **fields}
        with self.log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        if self._sqlite_store is not None:
            self._sqlite_store.record(self.run_id, ts, stage, event, fields)
