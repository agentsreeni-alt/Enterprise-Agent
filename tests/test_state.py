from enterprise_agent.connectors.base import JiraRef
from enterprise_agent.pipeline.gates import GateDecision, GateStatus
from enterprise_agent.pipeline.state import (
    BRDArtifact,
    PipelineState,
    PipelineStatus,
    new_run_id,
)


def test_round_trip_empty_state():
    state = PipelineState(run_id=new_run_id())
    restored = PipelineState.from_dict(state.to_dict())
    assert restored.run_id == state.run_id
    assert restored.status == PipelineStatus.RUNNING


def test_round_trip_with_artifacts():
    state = PipelineState(run_id=new_run_id())
    state.brd = BRDArtifact(
        template="default", tech_detail_level="medium", content="hello", follow_up_questions=["q1"]
    )
    state.jira_refs = [JiraRef(key="MOCK-1", url="https://x", title="t", kind="epic")]
    state.gate_history.append(
        GateDecision(
            stage="intake",
            status=GateStatus.APPROVED,
            reviewer="alice",
            comment=None,
            decided_at="2026-01-01T00:00:00+00:00",
        )
    )

    restored = PipelineState.from_dict(state.to_dict())
    assert restored.brd.content == "hello"
    assert restored.jira_refs[0].key == "MOCK-1"
    assert restored.gate_history[0].status is GateStatus.APPROVED
