"""Immutable audit log (control #5).

The orchestrator wraps every stage call with a start/end record automatically
-- stage authors never opt in or out. Each run gets its own append-only JSONL
file; no code path in this package rewrites or truncates it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditLogger:
    run_dir: Path

    @property
    def log_path(self) -> Path:
        return self.run_dir / "audit.log"

    def record(self, stage: str, event: str, **fields: Any) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _now_iso(), "stage": stage, "event": event, **fields}
        with self.log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
