"""Sandboxed execution (control #4).

Only Dev and Review agents run "inside" this — they're the two stages that
touch generated code. This scaffold's SandboxPolicy is bookkeeping only (it
records that a stage ran under a declared policy); it maps conceptually to
claude_agent_sdk's SandboxSettings for when these two stages get real,
LLM-driven, actually-isolated execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SandboxPolicy:
    no_network_to: list[str] = field(default_factory=lambda: ["prod", "production"])
    active: bool = False

    def __enter__(self) -> "SandboxPolicy":
        self.active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.active = False
