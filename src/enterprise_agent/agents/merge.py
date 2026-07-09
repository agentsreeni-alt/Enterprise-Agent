"""Stage 7: merge the approved PR to master. Pipeline terminates here --
production deployment is explicitly out of scope and never touched.
"""

from __future__ import annotations

from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import PipelineState


class MergeAgent(Stage):
    name = "merge"
    requires_gate = True
    connectors = ("github",)

    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        assert state.pr is not None, "MergeAgent requires an open PR"
        github = ctx.connectors["github"]
        state.merge_result = github.merge_pull_request(pr_id=state.pr.id)
        state.touch()
        return state
