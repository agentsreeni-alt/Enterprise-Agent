"""Tests for the web approval UI. Exercises the real Orchestrator.resume()
path through HTTP requests (fastapi.testclient.TestClient, in-process, no
real server/socket).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from enterprise_agent.pipeline.gates import GateStatus
from enterprise_agent.pipeline.orchestrator import Orchestrator
from enterprise_agent.pipeline.state import PipelineStatus
from enterprise_agent.pipeline.store import RunStore
from enterprise_agent.web.app import WEB_UI_TOKEN_ENV, create_app


def _client(tmp_path) -> tuple[TestClient, RunStore]:
    store = RunStore(runs_dir=tmp_path / "runs")
    app = create_app(store=store)
    return TestClient(app), store


def test_index_shows_no_runs_message(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No runs yet." in resp.text


def test_index_lists_a_started_run(tmp_path):
    client, store = _client(tmp_path)
    orch = Orchestrator(store=store)
    state = orch.start("fake transcript")

    resp = client.get("/")
    assert resp.status_code == 200
    assert state.run_id in resp.text


def test_run_detail_shows_approval_form_when_waiting(tmp_path):
    client, store = _client(tmp_path)
    orch = Orchestrator(store=store)
    state = orch.start("fake transcript")

    resp = client.get(f"/runs/{state.run_id}")
    assert resp.status_code == 200
    assert "Decision needed" in resp.text
    assert "waiting_for_approval" in resp.text


def test_run_detail_404_for_unknown_run(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404


def test_decide_approve_advances_the_run(tmp_path):
    client, store = _client(tmp_path)
    orch = Orchestrator(store=store)
    state = orch.start("fake transcript")

    resp = client.post(
        f"/runs/{state.run_id}/decide",
        data={"decision": "approved", "reviewer": "alice", "comment": "lgtm"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    updated = store.load_state(state.run_id)
    assert updated.gate_history[-1].status is GateStatus.APPROVED
    assert updated.gate_history[-1].reviewer == "alice"


def test_decide_reject_halts_the_run(tmp_path):
    client, store = _client(tmp_path)
    orch = Orchestrator(store=store)
    state = orch.start("fake transcript")

    client.post(
        f"/runs/{state.run_id}/decide",
        data={"decision": "rejected", "reviewer": "bob"},
        follow_redirects=False,
    )
    updated = store.load_state(state.run_id)
    assert updated.status is PipelineStatus.REJECTED


def test_auth_disabled_when_token_env_unset(tmp_path, monkeypatch):
    monkeypatch.delenv(WEB_UI_TOKEN_ENV, raising=False)
    client, _ = _client(tmp_path)
    assert client.get("/").status_code == 200


def test_auth_rejects_missing_or_wrong_token(tmp_path, monkeypatch):
    monkeypatch.setenv(WEB_UI_TOKEN_ENV, "secret123")
    client, _ = _client(tmp_path)
    assert client.get("/").status_code == 401
    assert client.get("/?token=wrong").status_code == 401
    assert client.get("/?token=secret123").status_code == 200


def test_html_escapes_untrusted_state_content(tmp_path):
    client, store = _client(tmp_path)
    orch = Orchestrator(store=store)
    state = orch.start("fake transcript")
    state.intake_summary = "<script>alert(1)</script>"
    store.save_state(state)

    resp = client.get(f"/runs/{state.run_id}")
    assert "<script>alert(1)</script>" not in resp.text
    assert "&lt;script&gt;" in resp.text
