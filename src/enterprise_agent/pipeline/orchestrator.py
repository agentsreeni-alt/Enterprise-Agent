"""Sequences the 8 stages, enforces gates, and wraps every stage call with
the security foundation: kill-switch check, audit logging, and connector
scoping. This wrapping happens here -- once -- rather than requiring every
stage author to remember to call into security/* themselves.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from enterprise_agent.agents.brd import BRDAgent
from enterprise_agent.agents.dev import DevAgent
from enterprise_agent.agents.docs import DocsAgent
from enterprise_agent.agents.intake import IntakeAgent
from enterprise_agent.agents.jira import JiraAgent
from enterprise_agent.agents.merge import MergeAgent
from enterprise_agent.agents.review import ReviewAgent
from enterprise_agent.agents.tdd import TDDAgent
from enterprise_agent.connectors.registry import get_connector
from enterprise_agent.pipeline.gates import GateDecision, GateStatus
from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import PipelineState, PipelineStatus, new_run_id
from enterprise_agent.pipeline.store import RunStore
from enterprise_agent.security.audit import AuditLogger
from enterprise_agent.security.kill_switch import KillSwitch
from enterprise_agent.security.vault import SecretsVault

STAGE_ORDER: list[Stage] = [
    IntakeAgent(),
    BRDAgent(),
    JiraAgent(),
    TDDAgent(),
    DevAgent(),
    ReviewAgent(),
    MergeAgent(),
    DocsAgent(),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GateRejectedError(RuntimeError):
    """Raised if resume() is called on a run that isn't waiting for approval."""


class Orchestrator:
    def __init__(
        self,
        store: RunStore | None = None,
        vault: SecretsVault | None = None,
        kill_switch: KillSwitch | None = None,
        connector_mode: str = "mock",
        connector_mode_overrides: dict[str, str] | None = None,
    ):
        self.store = store or RunStore()
        self.vault = vault or SecretsVault()
        self.kill_switch = kill_switch or KillSwitch()
        self.connector_mode = connector_mode
        # Per-connector-kind override, e.g. {"jira": "real"} to go live on
        # Jira while every other connector stays mocked. Defaults to {}, so
        # existing behavior (one global mode) is unaffected.
        self.connector_mode_overrides = connector_mode_overrides or {}

    def start(self, transcript_text: str) -> PipelineState:
        state = PipelineState(run_id=new_run_id(), transcript=transcript_text)
        return self._run_until_blocked(state)

    def resume(
        self,
        run_id: str,
        decision: GateStatus,
        reviewer: str | None = None,
        comment: str | None = None,
    ) -> PipelineState:
        state = self.store.load_state(run_id)
        if state.status is not PipelineStatus.WAITING_FOR_APPROVAL:
            raise GateRejectedError(
                f"run {run_id} is not waiting for approval (status={state.status.value})"
            )
        gated_stage = STAGE_ORDER[state.current_stage_index - 1].name
        state.gate_history.append(
            GateDecision(
                stage=gated_stage,
                status=decision,
                reviewer=reviewer,
                comment=comment,
                decided_at=_now_iso(),
            )
        )
        if decision is GateStatus.REJECTED:
            state.status = PipelineStatus.REJECTED
            state.touch()
            self.store.save_state(state)
            return state

        state.status = PipelineStatus.RUNNING
        return self._run_until_blocked(state)

    def _build_context(self, stage: Stage, run_id: str) -> StageContext:
        connectors = {
            kind: get_connector(
                kind, mode=self.connector_mode_overrides.get(kind, self.connector_mode)
            )
            for kind in stage.connectors
        }
        audit = AuditLogger(run_dir=self.store.run_dir(run_id))
        return StageContext(connectors=connectors, vault=self.vault, audit=audit)

    def _run_until_blocked(self, state: PipelineState) -> PipelineState:
        for stage in STAGE_ORDER[state.current_stage_index :]:
            if self.kill_switch.is_triggered():
                state.status = PipelineStatus.ABORTED
                state.touch()
                self.store.save_state(state)
                return state

            ctx = self._build_context(stage, state.run_id)
            ctx.audit.record(stage.name, "start")
            state = stage.run(state, ctx)
            ctx.audit.record(stage.name, "end")

            state.current_stage_index += 1
            state.touch()
            self.store.save_state(state)

            if stage.requires_gate:
                state.status = PipelineStatus.WAITING_FOR_APPROVAL
                state.touch()
                self.store.save_state(state)
                return state

        state.status = PipelineStatus.COMPLETED
        state.touch()
        self.store.save_state(state)
        return state
