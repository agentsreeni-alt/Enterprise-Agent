"""Stage 3: create Jira epics (large scope) or stories (small scope), linked
back to the BRD. No human gate -- ticket creation is low-risk/reversible.
"""

from __future__ import annotations

from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import PipelineState


class JiraAgent(Stage):
    name = "jira"
    requires_gate = False
    connectors = ("jira",)
    # Mirrors connectors/atlassian_mcp.JIRA_MCP_TOOL_ALLOWLIST as a plain,
    # dependency-free literal (not imported) so this module never pulls in
    # claude_agent_sdk even when only mock mode is used.
    agent_definition = {
        "description": "Creates Jira epics/stories from a BRD via Atlassian's remote MCP server.",
        "mcp_server": "atlassian",
        "allowed_tools": (
            "getAccessibleAtlassianResources",
            "getVisibleJiraProjects",
            "getJiraProjectIssueTypesMetadata",
            "createJiraIssue",
            "getJiraIssue",
        ),
    }

    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        jira = ctx.connectors["jira"]
        assert state.brd is not None, "JiraAgent requires a BRD to link against"

        epic = jira.create_epic(
            title="Feature epic (stub)",
            description=state.brd.content,
            brd_ref=state.run_id,
        )
        story = jira.create_story(
            title="Implement core flow (stub)",
            description=state.brd.content,
            epic_ref=epic.key,
        )
        state.jira_refs = [epic, story]
        state.touch()
        return state
