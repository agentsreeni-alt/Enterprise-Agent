"""PipelineState: the single object that flows through and accumulates every
artifact the pipeline produces, plus enough status/history to be persisted to
disk and resumed after a human gate (or a crash) pauses the run.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum

from enterprise_agent.connectors.base import DocLink, JiraRef, MergeResult, PullRequestRef
from enterprise_agent.pipeline.gates import GateDecision


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


class PipelineStatus(str, Enum):
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    REJECTED = "rejected"
    COMPLETED = "completed"
    ABORTED = "aborted"


@dataclass
class BRDArtifact:
    template: str
    tech_detail_level: str
    content: str
    follow_up_questions: list[str] = field(default_factory=list)


@dataclass
class TDDArtifact:
    stack: str
    content: str


@dataclass
class ReviewComment:
    file: str
    comment: str
    severity: str  # "blocking" | "suggestion"


@dataclass
class PipelineState:
    run_id: str
    status: PipelineStatus = PipelineStatus.RUNNING
    current_stage_index: int = 0
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    # accumulated artifacts, one field per hop in the pipeline's spine
    transcript: str | None = None
    intake_summary: str | None = None
    open_questions: list[str] = field(default_factory=list)
    brd: BRDArtifact | None = None
    jira_refs: list[JiraRef] = field(default_factory=list)
    tdd: TDDArtifact | None = None
    pr: PullRequestRef | None = None
    review_notes: list[ReviewComment] = field(default_factory=list)
    merge_result: MergeResult | None = None
    docs_links: list[DocLink] = field(default_factory=list)

    gate_history: list[GateDecision] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["gate_history"] = [g.to_dict() for g in self.gate_history]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineState":
        data = dict(data)
        data["status"] = PipelineStatus(data["status"])
        data["gate_history"] = [
            GateDecision.from_dict(g) for g in data.get("gate_history", [])
        ]
        if data.get("brd") is not None:
            data["brd"] = BRDArtifact(**data["brd"])
        if data.get("tdd") is not None:
            data["tdd"] = TDDArtifact(**data["tdd"])
        data["jira_refs"] = [JiraRef(**j) for j in data.get("jira_refs", [])]
        data["review_notes"] = [
            ReviewComment(**r) for r in data.get("review_notes", [])
        ]
        data["docs_links"] = [DocLink(**d_) for d_ in data.get("docs_links", [])]
        if data.get("pr") is not None:
            data["pr"] = PullRequestRef(**data["pr"])
        if data.get("merge_result") is not None:
            data["merge_result"] = MergeResult(**data["merge_result"])
        return cls(**data)
