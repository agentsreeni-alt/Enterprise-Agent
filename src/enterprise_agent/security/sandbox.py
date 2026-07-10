"""Sandboxed execution (control #4).

Only Dev and Review agents run "inside" this -- they're the two stages that
touch generated code.

`as_sandbox_settings()` produces a real `claude_agent_sdk.types.SandboxSettings`
(bash-command filesystem/network isolation) -- this is genuine, enforced
sandboxing once a stage actually runs an agentic claude_agent_sdk.query()
loop with tool access, which Dev/Review don't yet (they're still
deterministic stubs; see PROJECT_PLAN.md). Until then, `SandboxPolicy`'s
context-manager behavior remains bookkeeping only: it records that a stage
ran under a declared policy, nothing more -- stated here rather than
glossed over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SandboxPolicy:
    no_network_to: list[str] = field(default_factory=lambda: ["prod", "production"])
    active: bool = False

    def __enter__(self) -> "SandboxPolicy":
        self.active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.active = False

    def as_sandbox_settings(self) -> Any:
        """Real claude_agent_sdk SandboxSettings for this policy. Lazily
        imports claude_agent_sdk -- only called from a real, LLM-driven
        stage path, never from mock/stub mode.
        """
        from claude_agent_sdk.types import SandboxSettings

        settings: SandboxSettings = {
            "enabled": True,
            "network": {"deniedDomains": list(self.no_network_to)},
        }
        return settings
