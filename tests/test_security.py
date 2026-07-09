import json

from enterprise_agent.pipeline.gates import GateStatus
from enterprise_agent.pipeline.orchestrator import Orchestrator
from enterprise_agent.pipeline.state import PipelineStatus
from enterprise_agent.pipeline.store import RunStore
from enterprise_agent.security.guardrails import sanitize_output
from enterprise_agent.security.kill_switch import KillSwitch
from enterprise_agent.security.vault import SecretsVault


def test_sanitize_output_redacts_secrets():
    text = "contact me at person@example.com, api_key=sk_live_abcdefghijklmnop"
    sanitized = sanitize_output(text)
    assert "person@example.com" not in sanitized
    assert "sk_live_abcdefghijklmnop" not in sanitized


def test_scoped_token_never_exposes_value_in_redacted_view():
    token = SecretsVault().get_token("jira")
    redacted = token.redacted()
    assert "value" not in redacted
    assert redacted["scope"] == "jira"


def test_kill_switch_aborts_run(tmp_path):
    flag = tmp_path / "KILLSWITCH"
    ks = KillSwitch(flag_path=flag)
    ks.trigger("manual stop")
    assert ks.is_triggered()

    orch = Orchestrator(store=RunStore(runs_dir=tmp_path / "runs"), kill_switch=ks)
    state = orch.start("fake transcript")
    assert state.status is PipelineStatus.ABORTED
    assert state.current_stage_index == 0  # never even ran Intake


def test_audit_log_records_stage_boundaries(tmp_path):
    orch = Orchestrator(
        store=RunStore(runs_dir=tmp_path / "runs"),
        kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"),
    )
    state = orch.start("fake transcript")

    audit_path = tmp_path / "runs" / state.run_id / "audit.log"
    lines = audit_path.read_text().splitlines()
    entries = [json.loads(line) for line in lines]

    assert any(e["stage"] == "intake" and e["event"] == "start" for e in entries)
    assert any(e["stage"] == "intake" and e["event"] == "end" for e in entries)
    assert not any("token" in json.dumps(e).lower() for e in entries)
