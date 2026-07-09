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
        raise NotImplementedError(f"wire up real {kind} client here")
    if kind not in _MOCKS:
        raise ValueError(f"unknown connector kind: {kind}")
    return _MOCKS[kind]()
