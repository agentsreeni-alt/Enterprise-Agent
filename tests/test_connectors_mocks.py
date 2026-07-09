from enterprise_agent.connectors.mocks import (
    MockConfluenceConnector,
    MockGitHubConnector,
    MockJiraConnector,
    MockOtterConnector,
)


def test_otter_echoes_meeting_id():
    transcript = MockOtterConnector().get_transcript("m-123")
    assert transcript.meeting_id == "m-123"
    assert "m-123" in transcript.text


def test_jira_echoes_title():
    ref = MockJiraConnector().create_epic("My Epic", "desc", "brd-1")
    assert ref.title == "My Epic"
    assert ref.kind == "epic"
    assert ref.key.startswith("MOCK-")


def test_github_full_lifecycle():
    gh = MockGitHubConnector()
    pr = gh.open_pull_request("branch", "My PR", "body", "diff")
    gh.request_changes(pr.id, ["fix this"])
    result = gh.merge_pull_request(pr.id)
    assert result.pr_id == pr.id
    assert result.merged is True


def test_confluence_echoes_title():
    link = MockConfluenceConnector().publish_page("ENG", "My Page", "content")
    assert link.title == "My Page"
    assert "my-page" in link.url
