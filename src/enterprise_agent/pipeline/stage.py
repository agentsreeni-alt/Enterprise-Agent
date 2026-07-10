"""The common contract every one of the 8 subagents implements.

`Stage.connectors` is the least-privilege enforcement point: it declares
which connector kinds a stage may touch, and the orchestrator builds each
stage's StageContext containing only those connectors' scoped tokens. A
stage class can't reach a connector it didn't declare.

`agent_definition` is unused this pass (stages are deterministic stubs, not
LLM-driven) but reserved as the upgrade path: once a stage graduates to real
Claude Agent SDK-backed logic, this is where its AgentDefinition(description,
prompt, tools, ...) will live.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from enterprise_agent.pipeline.state import PipelineState
from enterprise_agent.security.audit import AuditLogger
from enterprise_agent.security.kill_switch import KillSwitch
from enterprise_agent.security.vault import SecretsVault


@dataclass
class StageContext:
    """Injected per-run, scoped to one stage: only the connectors that
    stage declared, never the whole world.
    """

    connectors: dict[str, Any]
    vault: SecretsVault
    audit: AuditLogger
    # "stub" (default): deterministic canned content, no SDK/network dependency.
    # "real": stage calls enterprise_agent.llm.run_prompt for real generation.
    llm_mode: str = "stub"
    # Lets a stage trigger an automated abort directly (e.g. a DLP hit on
    # content it's about to publish) -- see security/anomaly.py and
    # agents/docs.py. None in contexts that don't wire one up (e.g. direct
    # unit tests of a single stage).
    kill_switch: KillSwitch | None = None


class Stage(ABC):
    name: ClassVar[str]
    requires_gate: ClassVar[bool] = False
    connectors: ClassVar[tuple[str, ...]] = ()
    agent_definition: ClassVar[Any | None] = None

    @abstractmethod
    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        """Read prior artifacts off state, produce new artifacts, return the
        updated state. Must not mutate state in place in a way that would
        surprise a caller relying on the return value; returning `state`
        after in-place field updates is fine and is what the stub agents do.
        """
        raise NotImplementedError
