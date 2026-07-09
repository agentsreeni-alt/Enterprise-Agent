"""Manual, one-off verification script for the real Jira MCP connector.

Not part of the test suite (it makes real network calls against a real Jira
site and requires real credentials) -- run this yourself once
ENTERPRISE_AGENT_ATLASSIAN_SITE_URL (and either the API-token env vars or a
locally configured OAuth session) are set. See README.md's "Real Jira"
section for the required env vars.

Usage:
    python scripts/try_real_jira.py "Team discussed adding self-service password reset with SSO support."
"""

from __future__ import annotations

import sys

from enterprise_agent.pipeline.gates import GateStatus
from enterprise_agent.pipeline.orchestrator import Orchestrator
from enterprise_agent.pipeline.state import PipelineStatus


def main() -> int:
    transcript = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Team discussed adding self-service password reset with SSO support."
    )

    orch = Orchestrator(connector_mode_overrides={"jira": "real"})

    state = orch.start(transcript)
    print(f"run_id={state.run_id} status={state.status.value} (after Intake gate)")

    state = orch.resume(state.run_id, GateStatus.APPROVED, reviewer="try_real_jira.py")
    print(f"status={state.status.value} (after BRD gate -- Jira stage just ran)")

    if not state.jira_refs:
        print("FAILED: no jira_refs were populated.")
        return 1

    print(f"\nSUCCESS: {len(state.jira_refs)} real Jira issue(s) created:")
    for ref in state.jira_refs:
        print(f"  {ref.kind:5s} {ref.key}  {ref.url}")

    print(
        "\nConfirm these actually appear in your Jira project before trusting "
        "this connector in any automated context."
    )
    return 0 if state.status is not PipelineStatus.ABORTED else 1


if __name__ == "__main__":
    raise SystemExit(main())
