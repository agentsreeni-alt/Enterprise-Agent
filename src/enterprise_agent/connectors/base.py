"""Connector interfaces and the value types that flow across them.

Each Protocol here is the minimal contract a stage needs from an external
system. Mock implementations live in mocks.py; real API clients (swapped in
later via registry.get_connector(mode="real")) implement the same Protocols,
so no orchestrator/stage code has to change when a mock is replaced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Transcript:
    meeting_id: str
    text: str
    source: str = "otter"


@dataclass
class JiraRef:
    key: str
    url: str
    title: str
    kind: str  # "epic" | "story"


@dataclass
class PullRequestRef:
    id: str
    url: str
    branch: str
    title: str


@dataclass
class MergeResult:
    pr_id: str
    commit_sha: str
    merged: bool


@dataclass
class DocLink:
    url: str
    title: str
    space: str


class OtterConnector(Protocol):
    def get_transcript(self, meeting_id: str) -> Transcript: ...


class JiraConnector(Protocol):
    def create_epic(self, title: str, description: str, brd_ref: str) -> JiraRef: ...

    def create_story(
        self, title: str, description: str, epic_ref: str | None = None
    ) -> JiraRef: ...


class GitHubConnector(Protocol):
    def open_pull_request(
        self, branch: str, title: str, body: str, diff: str
    ) -> PullRequestRef: ...

    def request_changes(self, pr_id: str, comments: list[str]) -> None: ...

    def merge_pull_request(self, pr_id: str) -> MergeResult: ...


class ConfluenceConnector(Protocol):
    def publish_page(
        self, space: str, title: str, content: str, parent_id: str | None = None
    ) -> DocLink: ...
