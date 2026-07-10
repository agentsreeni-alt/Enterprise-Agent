"""Stage 8: publish BRD/TDD/release notes to Confluence. No gate -- purely
informational, post-merge.
"""

from __future__ import annotations

from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import PipelineState
from enterprise_agent.security.guardrails import count_redactions, sanitize_output


class DocsAgent(Stage):
    name = "docs"
    requires_gate = False
    connectors = ("confluence",)

    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        confluence = ctx.connectors["confluence"]
        assert state.brd is not None and state.tdd is not None

        redactions = count_redactions(state.brd.content) + count_redactions(state.tdd.content)
        ctx.audit.record(self.name, "dlp_scan", redactions=redactions)
        if redactions and ctx.kill_switch is not None:
            # Secret-shaped content about to leave via Confluence is itself
            # the anomaly -- don't publish it, abort the run instead.
            ctx.kill_switch.trigger(
                f"anomaly: {redactions} secret-shaped substring(s) redacted from "
                f"docs content on run {state.run_id}"
            )

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
