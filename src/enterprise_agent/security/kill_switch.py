"""Monitoring + kill switch (control #6).

Scaffold implementation is deliberately simple: presence of a flag file means
"triggered." A human (or a future automated anomaly-detection process) can
`touch` that file from any other terminal to stop a run between stages.

Known limitation, stated rather than glossed over: this can only interrupt
the orchestrator's between-stage loop, not a stage's own execution mid-call.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_FLAG_PATH = Path(".enterprise_agent/KILLSWITCH")


class KillSwitch:
    def __init__(self, flag_path: Path = DEFAULT_FLAG_PATH):
        self.flag_path = flag_path

    def is_triggered(self) -> bool:
        return self.flag_path.exists()

    def trigger(self, reason: str = "") -> None:
        self.flag_path.parent.mkdir(parents=True, exist_ok=True)
        self.flag_path.write_text(reason)

    def reset(self) -> None:
        self.flag_path.unlink(missing_ok=True)
