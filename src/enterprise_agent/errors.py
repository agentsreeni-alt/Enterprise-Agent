"""Shared base exception for every "real mode" failure (connector config,
connector call, or LLM generation).

Lets callers like the CLI catch any real-mode failure generically and print
a clean, actionable message instead of a raw traceback -- without having to
import the SDK-dependent modules that only load in real mode
(atlassian_mcp.py, github_mcp.py, notetaker.py, llm.py) just to reach their
exception classes. This module itself has zero dependencies beyond the
stdlib, so importing it never pulls in claude_agent_sdk.
"""

from __future__ import annotations


class RealModeError(RuntimeError):
    """Base for any error raised only when a stage/connector runs against a
    real external system instead of mock/stub. Never raised in mock mode.
    """
