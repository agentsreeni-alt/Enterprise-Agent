"""Regression test for a real bug: connector/LLM mode used to live only on
the in-memory Orchestrator instance. A CLI-driven run always spans multiple
separate processes (`run`, then a later `approve`), each constructing its
own fresh Orchestrator() -- so a run started in real mode would silently
fall back to mock/stub on its next gate unless the mode is persisted
per-run, on disk, and reloaded on resume().
"""

from __future__ import annotations

import json

from enterprise_agent.pipeline.gates import GateStatus
from enterprise_agent.pipeline.orchestrator import Orchestrator
from enterprise_agent.pipeline.store import RunStore
from enterprise_agent.security.kill_switch import KillSwitch


def _fake_run_prompt(prompt: str, system_prompt: str | None = None) -> str:
    # Intake's real-mode prompt expects JSON back; BRD's expects plain text.
    if "Business Requirements Document" in prompt:
        return "# Generated for real"
    return json.dumps({"summary": "s", "open_questions": []})


def test_llm_mode_survives_a_fresh_orchestrator_instance(tmp_path, monkeypatch):
    monkeypatch.setattr("enterprise_agent.llm.run_prompt", _fake_run_prompt)

    runs_dir = tmp_path / "runs"
    store = RunStore(runs_dir=runs_dir)

    # Process 1: `python -m enterprise_agent run --llm-real ...`
    orch_a = Orchestrator(
        store=store, kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"), llm_mode="real"
    )
    state = orch_a.start("fake transcript")

    config = store.load_config(state.run_id)
    assert config["llm_mode"] == "real"

    # Process 2: `python -m enterprise_agent approve ...` -- a brand new
    # Orchestrator with no llm_mode passed, defaulting to "stub".
    orch_b = Orchestrator(store=store, kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"))
    assert orch_b.llm_mode == "stub"  # confirms orch_b really does differ from orch_a

    state = orch_b.resume(state.run_id, GateStatus.APPROVED, reviewer="alice")  # past intake -> brd gate

    # If mode weren't persisted, BRD would have run under orch_b's "stub"
    # default and produced the canned stub string instead.
    assert state.brd.content == "# Generated for real"


def test_connector_mode_overrides_survive_a_fresh_orchestrator_instance(tmp_path):
    runs_dir = tmp_path / "runs"
    store = RunStore(runs_dir=runs_dir)

    orch_a = Orchestrator(
        store=store,
        kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"),
        connector_mode_overrides={"jira": "mock"},
    )
    state = orch_a.start("fake transcript")
    assert store.load_config(state.run_id)["connector_mode_overrides"] == {"jira": "mock"}

    orch_b = Orchestrator(store=store, kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"))
    assert orch_b.connector_mode_overrides == {}  # confirms orch_b really does differ

    state = orch_b.resume(state.run_id, GateStatus.APPROVED, reviewer="alice")  # past intake
    state = orch_b.resume(state.run_id, GateStatus.APPROVED, reviewer="alice")  # past brd -> jira runs
    assert len(state.jira_refs) == 2
