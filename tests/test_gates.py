import pytest

from enterprise_agent.pipeline.gates import GateStatus
from enterprise_agent.pipeline.orchestrator import GateRejectedError, Orchestrator
from enterprise_agent.pipeline.state import PipelineStatus
from enterprise_agent.pipeline.store import RunStore
from enterprise_agent.security.kill_switch import KillSwitch


def _orchestrator(tmp_path):
    return Orchestrator(
        store=RunStore(runs_dir=tmp_path / "runs"),
        kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"),
    )


def test_start_pauses_at_first_gate(tmp_path):
    orch = _orchestrator(tmp_path)
    state = orch.start("fake transcript")
    assert state.status is PipelineStatus.WAITING_FOR_APPROVAL
    assert state.current_stage_index == 1  # paused right after Intake (index 0)


def test_reject_halts_permanently(tmp_path):
    orch = _orchestrator(tmp_path)
    state = orch.start("fake transcript")
    state = orch.resume(state.run_id, GateStatus.REJECTED, reviewer="alice", comment="no")
    assert state.status is PipelineStatus.REJECTED

    with pytest.raises(GateRejectedError):
        orch.resume(state.run_id, GateStatus.APPROVED, reviewer="alice")


def test_approve_advances_to_next_gate(tmp_path):
    orch = _orchestrator(tmp_path)
    state = orch.start("fake transcript")
    state = orch.resume(state.run_id, GateStatus.APPROVED, reviewer="alice")
    # Jira (no gate) runs automatically, then BRD... wait, BRD is index 1, gate
    # after BRD -> should now be waiting again, past Jira? Order is
    # Intake(gate) -> BRD(gate) -> Jira -> TDD(gate) ...
    assert state.status is PipelineStatus.WAITING_FOR_APPROVAL
    assert state.gate_history[-1].stage == "intake"
