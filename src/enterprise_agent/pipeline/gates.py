"""Human approval gate types.

Five stages in the pipeline (Intake, BRD, TDD, Review, Merge) require an explicit
human decision before the orchestrator will proceed to the next stage. There is
no callback or web UI here — see orchestrator.py for the pause/resume mechanism,
which is just "persist state, exit; a later CLI invocation loads state and
continues."
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GateStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class GateDecision:
    stage: str
    status: GateStatus
    reviewer: str | None
    comment: str | None
    decided_at: str

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "status": self.status.value,
            "reviewer": self.reviewer,
            "comment": self.comment,
            "decided_at": self.decided_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GateDecision":
        return cls(
            stage=data["stage"],
            status=GateStatus(data["status"]),
            reviewer=data.get("reviewer"),
            comment=data.get("comment"),
            decided_at=data["decided_at"],
        )
