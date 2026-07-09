"""Network-free tests for the real-Jira gating path. No real credentials or
network calls happen here -- construction only validates config; the actual
MCP call happens inside create_epic/create_story, never invoked in these tests.
"""

import pytest

from enterprise_agent.agents.jira import JiraAgent
from enterprise_agent.connectors.atlassian_mcp import (
    AtlassianMcpConfigError,
    AtlassianMcpJiraConnector,
    SITE_URL_ENV,
)
from enterprise_agent.connectors.mocks import (
    MockConfluenceConnector,
    MockGitHubConnector,
    MockJiraConnector,
    MockOtterConnector,
)
from enterprise_agent.connectors.registry import get_connector


def test_mock_mode_unaffected_for_all_kinds():
    assert isinstance(get_connector("otter", mode="mock"), MockOtterConnector)
    assert isinstance(get_connector("jira", mode="mock"), MockJiraConnector)
    assert isinstance(get_connector("github", mode="mock"), MockGitHubConnector)
    assert isinstance(get_connector("confluence", mode="mock"), MockConfluenceConnector)


def test_real_jira_without_config_raises_actionable_error(monkeypatch):
    monkeypatch.delenv(SITE_URL_ENV, raising=False)
    with pytest.raises(AtlassianMcpConfigError, match="manual"):
        get_connector("jira", mode="real")


def test_real_jira_with_site_url_constructs_without_network(monkeypatch):
    monkeypatch.setenv(SITE_URL_ENV, "https://example.atlassian.net")
    connector = get_connector("jira", mode="real")
    assert isinstance(connector, AtlassianMcpJiraConnector)
    assert connector.site_url == "https://example.atlassian.net"


@pytest.mark.parametrize("kind", ["github", "confluence", "otter"])
def test_other_kinds_still_not_implemented_for_real_mode(kind):
    with pytest.raises(NotImplementedError):
        get_connector(kind, mode="real")


def test_jira_agent_declares_minimal_tool_allowlist():
    assert JiraAgent.agent_definition["allowed_tools"] == (
        "getAccessibleAtlassianResources",
        "getVisibleJiraProjects",
        "getJiraProjectIssueTypesMetadata",
        "createJiraIssue",
        "getJiraIssue",
    )
