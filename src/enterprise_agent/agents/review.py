"""Stage 6: diff the PR against the TDD + coding standards, flag issues.
Runs under SandboxPolicy like Dev; gated because a human must confirm the
review findings (or override them) before merge is attempted.
"""

from __future__ import annotations

from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import PipelineState, ReviewComment
from enterprise_agent.security.sandbox import SandboxPolicy


class ReviewAgent(Stage):
    name = "review"
    requires_gate = True
    connectors = ("github",)
    # Least privilege: Review only ever posts a review, never opens/merges PRs.
    agent_definition = {
        "description": "Diffs a PR against its TDD + standards and posts a review via GitHub's remote MCP server.",
        "mcp_server": "github",
        "allowed_tools": ("pull_request_review_write",),
    }

    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        assert state.pr is not None, "ReviewAgent requires an open PR"

        with SandboxPolicy():
            state.review_notes = [
                ReviewComment(
                    file="stub.diff",
                    comment="Looks consistent with the TDD (stub review).",
                    severity="suggestion",
                )
            ]
        state.touch()
        return state
