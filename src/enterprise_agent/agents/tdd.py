"""Stage 4: stack-aware Technical Design Document."""

from __future__ import annotations

from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import PipelineState, TDDArtifact


class TDDAgent(Stage):
    name = "tdd"
    requires_gate = True
    connectors = ()

    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        assert state.brd is not None, "TDDAgent requires a BRD"
        state.tdd = TDDArtifact(
            stack="node",
            content=(
                f"# Technical Design Document (stub)\n\n"
                f"Based on BRD:\n{state.brd.content}\n\n"
                f"Jira refs: {[j.key for j in state.jira_refs]}"
            ),
        )
        state.touch()
        return state
