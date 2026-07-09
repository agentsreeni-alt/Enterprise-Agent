"""Stage 5: implement in a sandboxed environment, open a PR only -- never
commit directly to a shared branch. No human gate at this stage itself
(review is the gate), but it runs under SandboxPolicy.
"""

from __future__ import annotations

from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import PipelineState
from enterprise_agent.security.sandbox import SandboxPolicy


class DevAgent(Stage):
    name = "dev"
    requires_gate = False
    connectors = ("github",)

    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        assert state.tdd is not None, "DevAgent requires a TDD"
        github = ctx.connectors["github"]

        with SandboxPolicy():
            diff = f"diff --stub-- implements TDD for stack={state.tdd.stack}"
            pr = github.open_pull_request(
                branch=f"agent/{state.run_id}",
                title="Implement feature (stub)",
                body=state.tdd.content,
                diff=diff,
            )
        state.pr = pr
        state.touch()
        return state
