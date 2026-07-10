"""Network-free tests for the real-connector gating paths. No real
credentials or network calls happen here -- construction only validates
config; the actual MCP call happens inside each connector's methods, never
invoked in these tests.
"""

import pytest

from enterprise_agent.agents.dev import DevAgent
from enterprise_agent.agents.jira import JiraAgent
from enterprise_agent.agents.merge import MergeAgent
from enterprise_agent.agents.review import ReviewAgent
from enterprise_agent.connectors.atlassian_mcp import (
    AtlassianMcpConfigError,
    AtlassianMcpConfluenceConnector,
    AtlassianMcpJiraConnector,
    SITE_URL_ENV,
)
from enterprise_agent.connectors.github_mcp import (
    GitHubMcpConfigError,
    GitHubMcpConnector,
    REPO_ENV,
    TOKEN_ENV,
)
from enterprise_agent.connectors.mocks import (
    MockConfluenceConnector,
    MockGitHubConnector,
    MockJiraConnector,
    MockOtterConnector,
)
from enterprise_agent.connectors.notetaker import (
    NotetakerConfigError,
    WebhookTranscriptConnector,
    ZoomTranscriptConnector,
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


def test_real_confluence_without_config_raises_actionable_error(monkeypatch):
    monkeypatch.delenv(SITE_URL_ENV, raising=False)
    with pytest.raises(AtlassianMcpConfigError, match="manual"):
        get_connector("confluence", mode="real")


def test_real_confluence_with_site_url_constructs_without_network(monkeypatch):
    monkeypatch.setenv(SITE_URL_ENV, "https://example.atlassian.net")
    connector = get_connector("confluence", mode="real")
    assert isinstance(connector, AtlassianMcpConfluenceConnector)
    assert connector.site_url == "https://example.atlassian.net"


def test_real_github_without_config_raises_actionable_error(monkeypatch):
    monkeypatch.delenv(REPO_ENV, raising=False)
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    with pytest.raises(GitHubMcpConfigError):
        get_connector("github", mode="real")


def test_real_github_with_config_constructs_without_network(monkeypatch):
    monkeypatch.setenv(REPO_ENV, "acme/widgets")
    monkeypatch.setenv(TOKEN_ENV, "fake-token")
    connector = get_connector("github", mode="real")
    assert isinstance(connector, GitHubMcpConnector)
    assert connector.owner == "acme"
    assert connector.repo == "widgets"
    assert connector.base_branch == "main"


def test_real_github_rejects_malformed_repo(monkeypatch):
    monkeypatch.setenv(REPO_ENV, "not-owner-slash-repo")
    monkeypatch.setenv(TOKEN_ENV, "fake-token")
    with pytest.raises(GitHubMcpConfigError, match="owner/repo"):
        get_connector("github", mode="real")


def test_real_otter_without_config_raises_actionable_error(monkeypatch):
    monkeypatch.delenv("ENTERPRISE_AGENT_TRANSCRIPT_SOURCE", raising=False)
    with pytest.raises(NotetakerConfigError):
        get_connector("otter", mode="real")


def test_real_otter_zoom_backend_constructs_without_network(monkeypatch):
    monkeypatch.setenv("ENTERPRISE_AGENT_TRANSCRIPT_SOURCE", "zoom")
    monkeypatch.setenv("ENTERPRISE_AGENT_ZOOM_ACCOUNT_ID", "acct")
    monkeypatch.setenv("ENTERPRISE_AGENT_ZOOM_CLIENT_ID", "cid")
    monkeypatch.setenv("ENTERPRISE_AGENT_ZOOM_CLIENT_SECRET", "secret")
    connector = get_connector("otter", mode="real")
    assert isinstance(connector, ZoomTranscriptConnector)


def test_real_otter_zoom_backend_requires_all_three_env_vars(monkeypatch):
    monkeypatch.setenv("ENTERPRISE_AGENT_TRANSCRIPT_SOURCE", "zoom")
    monkeypatch.delenv("ENTERPRISE_AGENT_ZOOM_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("ENTERPRISE_AGENT_ZOOM_CLIENT_ID", "cid")
    monkeypatch.setenv("ENTERPRISE_AGENT_ZOOM_CLIENT_SECRET", "secret")
    with pytest.raises(NotetakerConfigError):
        get_connector("otter", mode="real")


def test_real_otter_webhook_backend_constructs_without_network(monkeypatch):
    monkeypatch.setenv("ENTERPRISE_AGENT_TRANSCRIPT_SOURCE", "webhook")
    monkeypatch.setenv(
        "ENTERPRISE_AGENT_TRANSCRIPT_WEBHOOK_URL",
        "https://relay.example.com/transcripts/{meeting_id}",
    )
    connector = get_connector("otter", mode="real")
    assert isinstance(connector, WebhookTranscriptConnector)
    assert connector.url_template.format(meeting_id="m1") == (
        "https://relay.example.com/transcripts/m1"
    )


def test_real_otter_rejects_unknown_source(monkeypatch):
    monkeypatch.setenv("ENTERPRISE_AGENT_TRANSCRIPT_SOURCE", "carrier-pigeon")
    with pytest.raises(NotetakerConfigError):
        get_connector("otter", mode="real")


def test_jira_agent_declares_minimal_tool_allowlist():
    assert JiraAgent.agent_definition["allowed_tools"] == (
        "getAccessibleAtlassianResources",
        "getVisibleJiraProjects",
        "getJiraProjectIssueTypesMetadata",
        "createJiraIssue",
        "getJiraIssue",
    )


def test_github_stage_agents_declare_minimal_tool_allowlists():
    assert DevAgent.agent_definition["allowed_tools"] == (
        "create_branch",
        "create_or_update_file",
        "create_pull_request",
    )
    assert ReviewAgent.agent_definition["allowed_tools"] == ("pull_request_review_write",)
    assert MergeAgent.agent_definition["allowed_tools"] == ("merge_pull_request",)
