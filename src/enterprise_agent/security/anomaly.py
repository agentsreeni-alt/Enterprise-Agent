"""Automated anomaly detection (control #6's other half): triggers
`KillSwitch.trigger()` automatically instead of relying on a human to
notice something is wrong and `touch` the flag file.

Two real, independent signals, each wired at its natural source:

- Stage duration outliers: `DurationAnomalyDetector` compares a just-
  completed stage's wall-clock duration against the historical
  mean/stdev for that stage name, computed from the durable SQLite audit
  store (security/audit.py's `ENTERPRISE_AGENT_AUDIT_DB`). Requires that
  store to be configured -- with only the per-run JSONL file, there's no
  cross-run history to compare against. The orchestrator checks this
  between stages, same limitation as every other kill-switch check
  (security/kill_switch.py): it can't interrupt a stage's own execution
  mid-call.
- DLP redactions: any stage that calls
  `security.guardrails.count_redactions()` on content it's about to
  publish/persist and gets a nonzero count can trigger the kill switch
  directly via `StageContext.kill_switch` -- see agents/docs.py.
"""

from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class DurationAnomalyDetector:
    threshold_stdevs: float = 3.0
    min_samples: int = 3

    def _historical_durations(self, db_path: Path, stage: str, exclude_run_id: str) -> list[float]:
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT run_id, event, ts FROM audit_log WHERE stage = ? AND run_id != ? "
                "AND event IN ('start', 'end') ORDER BY run_id, ts",
                (stage, exclude_run_id),
            ).fetchall()
        finally:
            conn.close()

        by_run: dict[str, dict[str, str]] = {}
        for run_id, event, ts in rows:
            by_run.setdefault(run_id, {})[event] = ts

        durations = []
        for events in by_run.values():
            if "start" in events and "end" in events:
                start = datetime.fromisoformat(events["start"])
                end = datetime.fromisoformat(events["end"])
                durations.append((end - start).total_seconds())
        return durations

    def check(
        self, db_path: Path, stage: str, run_id: str, duration_seconds: float
    ) -> str | None:
        """Returns a human-readable reason if `duration_seconds` is an
        outlier vs. this stage's history, else None. Never raises on a
        missing/empty database -- anomaly detection degrading to a no-op
        must never be able to break a run.
        """
        try:
            durations = self._historical_durations(db_path, stage, run_id)
        except sqlite3.Error:
            return None
        if len(durations) < self.min_samples:
            return None

        mean = statistics.mean(durations)
        # Floor stdev so a history of near-identical durations (stdev ~= 0)
        # doesn't disable detection entirely -- a stage that always takes
        # ~10s and suddenly takes 500s is exactly the case this exists to
        # catch, not one to skip because the variance happens to be zero.
        stdev = max(statistics.pstdev(durations), mean * 0.05, 0.01)
        threshold = mean + self.threshold_stdevs * stdev
        if duration_seconds <= threshold:
            return None
        return (
            f"anomaly: stage {stage!r} took {duration_seconds:.1f}s, "
            f"more than {self.threshold_stdevs} stdevs over its historical "
            f"mean of {mean:.1f}s (n={len(durations)})"
        )
