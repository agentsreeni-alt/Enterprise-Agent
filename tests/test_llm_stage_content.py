"""Tests for llm_mode="real" stage content generation. No real credentials
or network calls happen here -- enterprise_agent.llm.run_prompt is
monkeypatched per stage, so claude_agent_sdk.query is never invoked.
"""

from __future__ import annotations

import json

from enterprise_agent.agents.brd import BRDAgent
from enterprise_agent.agents.intake import IntakeAgent
from enterprise_agent.agents.review import ReviewAgent
from enterprise_agent.agents.tdd import TDDAgent
from enterprise_agent.connectors.base import PullRequestRef
from enterprise_agent.connectors.mocks import MockOtterConnector
from enterprise_agent.pipeline.stage import StageContext
from enterprise_agent.pipeline.state import BRDArtifact, PipelineState
from enterprise_agent.security.audit import AuditLogger
from enterprise_agent.security.vault import SecretsVault


def _ctx(tmp_path, connectors=None, llm_mode="real") -> StageContext:
    return StageContext(
        connectors=connectors or {},
        vault=SecretsVault(),
        audit=AuditLogger(run_dir=tmp_path),
        llm_mode=llm_mode,
    )


def test_intake_real_mode_parses_llm_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "enterprise_agent.llm.run_prompt",
        lambda prompt, system_prompt=None: json.dumps(
            {"summary": "Real summary", "open_questions": ["Q1?"]}
        ),
    )
    state = PipelineState(run_id="r1")
    ctx = _ctx(tmp_path, connectors={"otter": MockOtterConnector()})
    state = IntakeAgent().run(state, ctx)
    assert state.intake_summary == "Real summary"
    assert state.open_questions == ["Q1?"]


def test_brd_real_mode_uses_llm_content(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "enterprise_agent.llm.run_prompt",
        lambda prompt, system_prompt=None: "# Real BRD",
    )
    state = PipelineState(run_id="r1", intake_summary="s", open_questions=["q"])
    ctx = _ctx(tmp_path)
    state = BRDAgent().run(state, ctx)
    assert state.brd.content == "# Real BRD"
    assert state.brd.follow_up_questions == ["q"]


def test_tdd_real_mode_parses_llm_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "enterprise_agent.llm.run_prompt",
        lambda prompt, system_prompt=None: json.dumps(
            {"stack": "python", "content": "# Real TDD"}
        ),
    )
    state = PipelineState(run_id="r1")
    state.brd = BRDArtifact(template="default", tech_detail_level="medium", content="brd")
    ctx = _ctx(tmp_path)
    state = TDDAgent().run(state, ctx)
    assert state.tdd.stack == "python"
    assert state.tdd.content == "# Real TDD"


def test_review_real_mode_parses_llm_json_array(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "enterprise_agent.llm.run_prompt",
        lambda prompt, system_prompt=None: json.dumps(
            [{"file": "a.py", "comment": "missing test", "severity": "blocking"}]
        ),
    )
    state = PipelineState(run_id="r1", dev_diff="diff --stub--")
    state.tdd = None
    state.pr = PullRequestRef(id="1", url="https://x", branch="b", title="t")
    ctx = _ctx(tmp_path)
    state = ReviewAgent().run(state, ctx)
    assert len(state.review_notes) == 1
    assert state.review_notes[0].file == "a.py"
    assert state.review_notes[0].severity == "blocking"


def test_stub_mode_is_still_the_default(tmp_path):
    state = PipelineState(run_id="r1")
    ctx = _ctx(tmp_path, connectors={"otter": MockOtterConnector()}, llm_mode="stub")
    state = IntakeAgent().run(state, ctx)
    assert state.intake_summary.startswith("Summary (stub)")
