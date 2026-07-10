"""Connector factory. mode="real" is an explicit, impossible-to-silently-skip
placeholder for future API-client integration work.
"""

from __future__ import annotations

from typing import Literal

from enterprise_agent.connectors.mocks import (
    MockConfluenceConnector,
    MockGitHubConnector,
    MockJiraConnector,
    MockOtterConnector,
)

ConnectorKind = Literal["otter", "jira", "github", "confluence"]
ConnectorMode = Literal["mock", "real"]

_MOCKS = {
    "otter": MockOtterConnector,
    "jira": MockJiraConnector,
    "github": MockGitHubConnector,
    "confluence": MockConfluenceConnector,
}


def get_connector(kind: ConnectorKind, mode: ConnectorMode = "mock"):
    if mode == "real":
        if kind == "jira":
            # Local import: mock-mode runs (all other kinds, all tests) must
            # never load claude_agent_sdk or depend on it being installed.
            from enterprise_agent.connectors.atlassian_mcp import (
                build_real_jira_connector,
            )

            return build_real_jira_connector()
        if kind == "confluence":
            from enterprise_agent.connectors.atlassian_mcp import (
                build_real_confluence_connector,
            )

            return build_real_confluence_connector()
        if kind == "github":
            from enterprise_agent.connectors.github_mcp import (
                build_real_github_connector,
            )

            return build_real_github_connector()
        if kind == "otter":
            from enterprise_agent.connectors.notetaker import (
                build_real_notetaker_connector,
            )

            return build_real_notetaker_connector()
        raise NotImplementedError(f"wire up real {kind} client here")
    if kind not in _MOCKS:
        raise ValueError(f"unknown connector kind: {kind}")
    return _MOCKS[kind]()
