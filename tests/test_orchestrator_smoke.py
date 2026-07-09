"""End-to-end proof: drive the full pipeline through all 5 gates using only
mocks/fixtures -- no network, no credentials.
"""

from enterprise_agent.pipeline.gates import GateStatus
from enterprise_agent.pipeline.orchestrator import Orchestrator
from enterprise_agent.pipeline.state import PipelineStatus
from enterprise_agent.pipeline.store import RunStore
from enterprise_agent.security.kill_switch import KillSwitch


def test_full_pipeline_runs_to_completion(tmp_path):
    orch = Orchestrator(
        store=RunStore(runs_dir=tmp_path / "runs"),
        kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"),
    )

    state = orch.start("Product owner: we need a password reset flow.")

    # Drive through every gate until the run completes or aborts.
    guard = 0
    while state.status is PipelineStatus.WAITING_FOR_APPROVAL:
        guard += 1
        assert guard <= 10, "too many gates encountered; possible infinite loop"
        state = orch.resume(state.run_id, GateStatus.APPROVED, reviewer="alice", comment="lgtm")

    assert state.status is PipelineStatus.COMPLETED
    assert state.current_stage_index == 8

    # Every artifact field the diagram's spine promises must be populated.
    assert state.intake_summary
    assert state.open_questions
    assert state.brd is not None and state.brd.content
    assert len(state.jira_refs) == 2
    assert state.tdd is not None and state.tdd.content
    assert state.pr is not None
    assert len(state.review_notes) == 1
    assert state.merge_result is not None and state.merge_result.merged
    assert len(state.docs_links) == 2

    # 5 gates: intake, brd, tdd, review, merge
    gated_stages = [g.stage for g in state.gate_history]
    assert gated_stages == ["intake", "brd", "tdd", "review", "merge"]


def test_rejecting_a_gate_halts_the_pipeline(tmp_path):
    orch = Orchestrator(
        store=RunStore(runs_dir=tmp_path / "runs"),
        kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"),
    )
    state = orch.start("Some transcript.")
    state = orch.resume(state.run_id, GateStatus.APPROVED, reviewer="alice")  # past intake
    state = orch.resume(
        state.run_id, GateStatus.REJECTED, reviewer="alice", comment="not ready"
    )  # reject at BRD gate

    assert state.status is PipelineStatus.REJECTED
    assert state.current_stage_index == 2  # stopped right after BRD, never ran Jira/TDD
