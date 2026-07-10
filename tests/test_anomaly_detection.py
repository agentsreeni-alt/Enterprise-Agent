"""Tests for automated kill-switch triggers: stage-duration outliers
(security/anomaly.py) and DLP-redaction hits (agents/docs.py). No network
calls -- everything here is local SQLite/filesystem state.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from enterprise_agent.agents.docs import DocsAgent
from enterprise_agent.connectors.mocks import MockConfluenceConnector
from enterprise_agent.pipeline.gates import GateStatus
from enterprise_agent.pipeline.orchestrator import Orchestrator
from enterprise_agent.pipeline.stage import StageContext
from enterprise_agent.pipeline.state import BRDArtifact, PipelineState, PipelineStatus, TDDArtifact
from enterprise_agent.pipeline.store import RunStore
from enterprise_agent.security.anomaly import DurationAnomalyDetector
from enterprise_agent.security.audit import AUDIT_DB_ENV, AuditLogger
from enterprise_agent.security.kill_switch import KillSwitch
from enterprise_agent.security.vault import SecretsVault


def _seed_history(db_path: Path, stage: str, run_id: str, start: datetime, duration_s: float) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "run_id TEXT, ts TEXT, stage TEXT, event TEXT, fields_json TEXT)"
    )
    conn.execute(
        "INSERT INTO audit_log (run_id, ts, stage, event, fields_json) VALUES (?, ?, ?, 'start', '{}')",
        (run_id, start.isoformat(), stage),
    )
    conn.execute(
        "INSERT INTO audit_log (run_id, ts, stage, event, fields_json) VALUES (?, ?, ?, 'end', '{}')",
        (run_id, (start + timedelta(seconds=duration_s)).isoformat(), stage),
    )
    conn.commit()
    conn.close()


def test_duration_detector_flags_outlier_vs_history(tmp_path):
    db_path = tmp_path / "audit.db"
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        _seed_history(db_path, "intake", f"run-{i}", base, duration_s=10.0)

    detector = DurationAnomalyDetector(threshold_stdevs=3.0, min_samples=3)
    reason = detector.check(db_path, "intake", "run-current", duration_seconds=500.0)
    assert reason is not None
    assert "intake" in reason


def test_duration_detector_does_not_flag_normal_duration(tmp_path):
    db_path = tmp_path / "audit.db"
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        _seed_history(db_path, "intake", f"run-{i}", base, duration_s=10.0)

    detector = DurationAnomalyDetector(threshold_stdevs=3.0, min_samples=3)
    reason = detector.check(db_path, "intake", "run-current", duration_seconds=11.0)
    assert reason is None


def test_duration_detector_requires_min_samples(tmp_path):
    db_path = tmp_path / "audit.db"
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _seed_history(db_path, "intake", "run-0", base, duration_s=10.0)

    detector = DurationAnomalyDetector(threshold_stdevs=3.0, min_samples=3)
    reason = detector.check(db_path, "intake", "run-current", duration_seconds=999.0)
    assert reason is None


def test_duration_detector_handles_missing_db_gracefully(tmp_path):
    detector = DurationAnomalyDetector()
    reason = detector.check(tmp_path / "does-not-exist.db", "intake", "run-x", 5.0)
    assert reason is None


def test_docs_agent_triggers_kill_switch_on_dlp_hit(tmp_path):
    ks = KillSwitch(flag_path=tmp_path / "KILLSWITCH")
    ctx = StageContext(
        connectors={"confluence": MockConfluenceConnector()},
        vault=SecretsVault(),
        audit=AuditLogger(run_dir=tmp_path / "run1"),
        kill_switch=ks,
    )
    state = PipelineState(run_id="run1")
    state.brd = BRDArtifact(
        template="default",
        tech_detail_level="medium",
        content="contact person@example.com for the api_key=sk_live_abcdefghijklmnop",
    )
    state.tdd = TDDArtifact(stack="node", content="no secrets here")

    assert not ks.is_triggered()
    DocsAgent().run(state, ctx)
    assert ks.is_triggered()


def test_docs_agent_does_not_trigger_kill_switch_when_clean(tmp_path):
    ks = KillSwitch(flag_path=tmp_path / "KILLSWITCH")
    ctx = StageContext(
        connectors={"confluence": MockConfluenceConnector()},
        vault=SecretsVault(),
        audit=AuditLogger(run_dir=tmp_path / "run1"),
        kill_switch=ks,
    )
    state = PipelineState(run_id="run1")
    state.brd = BRDArtifact(template="default", tech_detail_level="medium", content="clean content")
    state.tdd = TDDArtifact(stack="node", content="also clean")

    DocsAgent().run(state, ctx)
    assert not ks.is_triggered()


class _AlwaysAnomalous:
    def check(self, db_path, stage, run_id, duration_seconds):
        return f"forced anomaly on {stage}"


def test_orchestrator_aborts_next_stage_after_duration_anomaly(tmp_path, monkeypatch):
    monkeypatch.setenv(AUDIT_DB_ENV, str(tmp_path / "audit.db"))
    orch = Orchestrator(
        store=RunStore(runs_dir=tmp_path / "runs"),
        kill_switch=KillSwitch(flag_path=tmp_path / "KILLSWITCH"),
        anomaly_detector=_AlwaysAnomalous(),
    )
    state = orch.start("fake transcript")
    # Intake ran (and was flagged as anomalous), then paused at its gate --
    # the kill switch trips between stages, so it fires on the *next* run.
    assert state.status is PipelineStatus.WAITING_FOR_APPROVAL
    assert orch.kill_switch.is_triggered()

    resumed = orch.resume(state.run_id, GateStatus.APPROVED, reviewer="alice")
    assert resumed.status is PipelineStatus.ABORTED
