"""Mock connectors: canned, input-echoing fake data.

These exist so the pipeline's control flow and state accumulation can be
tested and demoed with zero credentials and zero network calls. Each mock
echoes its inputs into the fake reference it returns (e.g. a Jira key that
includes the real title) so tests can assert genuine data flow, not just
"the call didn't crash."
"""

from __future__ import annotations

import itertools

from enterprise_agent.connectors.base import (
    DocLink,
    JiraRef,
    MergeResult,
    PullRequestRef,
    Transcript,
)


class MockOtterConnector:
    def get_transcript(self, meeting_id: str) -> Transcript:
        return Transcript(
            meeting_id=meeting_id,
            text=(
                f"[MOCK TRANSCRIPT for meeting {meeting_id}]\n"
                "Product owner: We need a self-service password reset flow. "
                "Engineering: Should support SSO users too. "
                "Open question: what's the rate limit on reset requests?"
            ),
        )


class MockJiraConnector:
    def __init__(self) -> None:
        self._counter = itertools.count(1)

    def create_epic(self, title: str, description: str, brd_ref: str) -> JiraRef:
        n = next(self._counter)
        return JiraRef(
            key=f"MOCK-{n}",
            url=f"https://mock.atlassian.net/browse/MOCK-{n}",
            title=title,
            kind="epic",
        )

    def create_story(
        self, title: str, description: str, epic_ref: str | None = None
    ) -> JiraRef:
        n = next(self._counter)
        return JiraRef(
            key=f"MOCK-{n}",
            url=f"https://mock.atlassian.net/browse/MOCK-{n}",
            title=title,
            kind="story",
        )


class MockGitHubConnector:
    """A fresh instance is created per stage call (mirroring how a real API
    client would be instantiated per-process). Unlike a stateful mock backed
    by an in-memory dict, this doesn't try to be the source of truth for
    which PRs "exist" -- a real GitHub server remembers PRs across process
    boundaries; this mock simply trusts the pr_id it's given, the same way a
    real client would trust GitHub's response.
    """

    def __init__(self) -> None:
        self._counter = itertools.count(1)

    def open_pull_request(
        self, branch: str, title: str, body: str, diff: str
    ) -> PullRequestRef:
        n = next(self._counter)
        return PullRequestRef(
            id=f"PR-{n}",
            url=f"https://github.com/mock/enterprise-agent/pull/{n}",
            branch=branch,
            title=title,
        )

    def request_changes(self, pr_id: str, comments: list[str]) -> None:
        pass

    def merge_pull_request(self, pr_id: str) -> MergeResult:
        return MergeResult(pr_id=pr_id, commit_sha=f"mockcommit{pr_id}", merged=True)


class MockConfluenceConnector:
    def publish_page(
        self, space: str, title: str, content: str, parent_id: str | None = None
    ) -> DocLink:
        slug = title.lower().replace(" ", "-")
        return DocLink(
            url=f"https://mock.atlassian.net/wiki/spaces/{space}/{slug}",
            title=title,
            space=space,
        )
