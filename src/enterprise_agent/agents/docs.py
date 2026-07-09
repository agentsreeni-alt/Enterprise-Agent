"""Stage 8: publish BRD/TDD/release notes to Confluence. No gate -- purely
informational, post-merge.
"""

from __future__ import annotations

from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import PipelineState
from enterprise_agent.security.guardrails import sanitize_output


class DocsAgent(Stage):
    name = "docs"
    requires_gate = False
    connectors = ("confluence",)

    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        confluence = ctx.connectors["confluence"]
        assert state.brd is not None and state.tdd is not None

        brd_link = confluence.publish_page(
            space="ENG",
            title=f"BRD - run {state.run_id}",
            content=sanitize_output(state.brd.content),
        )
        tdd_link = confluence.publish_page(
            space="ENG",
            title=f"TDD - run {state.run_id}",
            content=sanitize_output(state.tdd.content),
        )
        state.docs_links = [brd_link, tdd_link]
        state.touch()
        return state
