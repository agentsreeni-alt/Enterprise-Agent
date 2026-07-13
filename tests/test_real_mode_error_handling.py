"""Regression tests for a real usability bug found live: a real-mode
connector failure (e.g. blocked network egress to a real MCP server) used
to surface as a raw Python traceback through the CLI and a 500 through the
web UI instead of a clean, actionable error. Every real-mode exception now
shares a common RealModeError base the CLI/web layer can catch generically
without importing the SDK-dependent modules that define the concrete
exception classes.
"""

from __future__ import annotations

import sys

import pytest

from enterprise_agent.errors import RealModeError


def test_atlassian_errors_are_real_mode_errors():
    from enterprise_agent.connectors.atlassian_mcp import (
        AtlassianMcpConfigError,
        AtlassianMcpToolCallError,
    )

    assert issubclass(AtlassianMcpConfigError, RealModeError)
    assert issubclass(AtlassianMcpToolCallError, RealModeError)


def test_github_errors_are_real_mode_errors():
    from enterprise_agent.connectors.github_mcp import (
        GitHubMcpConfigError,
        GitHubMcpToolCallError,
    )

    assert issubclass(GitHubMcpConfigError, RealModeError)
    assert issubclass(GitHubMcpToolCallError, RealModeError)


def test_notetaker_errors_are_real_mode_errors():
    from enterprise_agent.connectors.notetaker import (
        NotetakerConfigError,
        NotetakerRequestError,
    )

    assert issubclass(NotetakerConfigError, RealModeError)
    assert issubclass(NotetakerRequestError, RealModeError)


def test_llm_output_error_is_a_real_mode_error_and_still_a_value_error():
    from enterprise_agent.llm import LLMOutputError

    assert issubclass(LLMOutputError, RealModeError)
    assert issubclass(LLMOutputError, ValueError)  # unchanged for existing callers


def test_errors_module_never_imports_claude_agent_sdk():
    """The whole point of the shared base living in its own module: cli.py
    can catch RealModeError without loading claude_agent_sdk.
    """
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", "import enterprise_agent.errors; import sys; "
         "assert 'claude_agent_sdk' not in sys.modules, 'errors.py pulled in the SDK'"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_cli_run_reports_clean_error_on_real_mode_failure(tmp_path, monkeypatch, capsys):
    from enterprise_agent import cli
    from enterprise_agent.connectors.atlassian_mcp import AtlassianMcpConfigError

    transcript = tmp_path / "t.txt"
    transcript.write_text("hello")
    monkeypatch.setenv("ENTERPRISE_AGENT_ATLASSIAN_SITE_URL", "")
    monkeypatch.delenv("ENTERPRISE_AGENT_ATLASSIAN_SITE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    def fake_start(self, text):
        raise AtlassianMcpConfigError("simulated: site URL not set")

    monkeypatch.setattr("enterprise_agent.pipeline.orchestrator.Orchestrator.start", fake_start)

    exit_code = cli.main(["run", "--input", str(transcript), "--real", "jira"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "simulated: site URL not set" in captured.err
    assert "Traceback" not in captured.err
