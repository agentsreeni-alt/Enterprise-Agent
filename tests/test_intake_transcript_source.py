"""Regression tests for a real bug found during manual testing:
Orchestrator.start(transcript_text) sets state.transcript, but IntakeAgent
used to unconditionally overwrite it by fetching from the otter connector
-- so `python -m enterprise_agent run --input file.txt` had no effect on
what actually flowed into the pipeline. IntakeAgent must now prefer an
already-supplied transcript and only fall back to the connector when none
was given.
"""

from __future__ import annotations

from enterprise_agent.agents.intake import IntakeAgent
from enterprise_agent.pipeline.orchestrator import Orchestrator
from enterprise_agent.pipeline.stage import StageContext
from enterprise_agent.pipeline.state import PipelineState, PipelineStatus
from enterprise_agent.pipeline.store import RunStore
from enterprise_agent.security.audit import AuditLogger
from enterprise_agent.security.kill_switch import KillSwitch
from enterprise_agent.security.vault import SecretsVault


class _ExplodingOtterConnector:
    """Fails the test if IntakeAgent calls it -- proves the caller-supplied
    transcript path never touches the connector.
    """

    def get_transcript(self, meeting_id: str):
        raise AssertionError("otter connector should not be called when a transcript was supplied")


def _ctx(tmp_path, connectors) -> StageContext:
    return StageContext(
        connectors=connectors, vault=SecretsVault(), audit=AuditLogger(run_dir=tmp_path)
    )


def test_intake_honors_caller_supplied_transcript(tmp_path):
    state = PipelineState(run_id="r1", transcript="Team discussed X, Y, and Z.")
    ctx = _ctx(tmp_path, connectors={"otter": _ExplodingOtterConnector()})
    result = IntakeAgent().run(state, ctx)
    assert "Team discussed X, Y, and Z." in result.transcript


def test_intake_falls_back_to_connector_when_no_transcript_supplied(tmp_path):
    from enterprise_agent.connectors.mocks import MockOtterConnector

    state = PipelineState(run_id="r1")  # no transcript
    ctx = _ctx(tmp_path, connectors={"otter": MockOtterConnector()})
    result = IntakeAgent().run(state, ctx)
    assert "MOCK TRANSCRIPT" in result.transcript


def test_cli_style_start_actually_uses_the_supplied_transcript_text(tmp_path):
    """End-to-end: two different transcripts fed into start() must not
    collapse to the same intake output -- the specific regression this
    guards against.
    """
    orch = Orchestrator(
        store=RunStore(runs_dir=tmp_path / "runs"),
        kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"),
    )
    state_a = orch.start("Alpha scenario: SSO password reset rate limiting.")
    state_b = orch.start("Beta scenario: a completely unrelated billing export bug.")

    assert state_a.status is PipelineStatus.WAITING_FOR_APPROVAL
    assert state_b.status is PipelineStatus.WAITING_FOR_APPROVAL
    assert "Alpha scenario" in state_a.transcript
    assert "Beta scenario" in state_b.transcript
    assert state_a.transcript != state_b.transcript
