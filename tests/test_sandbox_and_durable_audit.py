"""Tests for SandboxPolicy.as_sandbox_settings() and the optional SQLite
durable audit store. No real sandboxing/network isolation is exercised
here (that only happens inside a live claude_agent_sdk.query() loop) --
this only checks the settings object shape and the DB write path.
"""

from __future__ import annotations

import sqlite3

from enterprise_agent.security.audit import AUDIT_DB_ENV, AuditLogger
from enterprise_agent.security.sandbox import SandboxPolicy


def test_sandbox_policy_context_manager_still_works():
    policy = SandboxPolicy()
    assert policy.active is False
    with policy:
        assert policy.active is True
    assert policy.active is False


def test_as_sandbox_settings_maps_no_network_to_denied_domains():
    policy = SandboxPolicy(no_network_to=["prod", "production"])
    settings = policy.as_sandbox_settings()
    assert settings["enabled"] is True
    assert settings["network"]["deniedDomains"] == ["prod", "production"]


def test_audit_logger_writes_jsonl_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv(AUDIT_DB_ENV, raising=False)
    logger = AuditLogger(run_dir=tmp_path / "run1")
    logger.record("intake", "start")
    assert (tmp_path / "run1" / "audit.log").exists()


def test_audit_logger_also_writes_to_sqlite_when_configured(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    monkeypatch.setenv(AUDIT_DB_ENV, str(db_path))
    logger = AuditLogger(run_dir=tmp_path / "run1")
    logger.record("intake", "start", extra="field")

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT run_id, stage, event FROM audit_log").fetchall()
    conn.close()

    assert rows == [("run1", "intake", "start")]
    # JSONL is still written alongside SQLite, not instead of it.
    assert (tmp_path / "run1" / "audit.log").exists()
