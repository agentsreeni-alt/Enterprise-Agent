"""Stage 2: generate a Business Requirements Document from the intake summary."""

from __future__ import annotations

from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import BRDArtifact, PipelineState


class BRDAgent(Stage):
    name = "brd"
    requires_gate = True
    connectors = ()

    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        state.brd = BRDArtifact(
            template="default",
            tech_detail_level="medium",
            content=(
                f"# Business Requirements Document (stub)\n\n"
                f"Summary: {state.intake_summary}\n\n"
                f"Open questions carried forward: {', '.join(state.open_questions)}"
            ),
            follow_up_questions=list(state.open_questions),
        )
        state.touch()
        return state
