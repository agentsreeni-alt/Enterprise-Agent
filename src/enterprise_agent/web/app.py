"""Web approval UI: replaces CLI-only `approve`/`reject` with a browser
gate reviewers can use directly, while keeping every write going through
the same `Orchestrator.resume()` path the CLI uses -- this is a different
front door onto the same gate semantics, not a parallel implementation of
them.

Deliberately not imported by anything else in this package (cli.py imports
it lazily inside `serve`) so the base install/test suite doesn't require
fastapi/uvicorn unless a run actually launches the server.

Auth: a single shared token (`ENTERPRISE_AGENT_WEB_UI_TOKEN`), checked on
every request. This is intentionally coarse -- real SSO/per-user identity
is a known limitation (see PROJECT_PLAN.md), not attempted here. If the env
var is unset, auth is a no-op: fine for local/dev use on localhost, never
for anything reachable beyond that.
"""

from __future__ import annotations

import html
import os

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from enterprise_agent.errors import RealModeError
from enterprise_agent.pipeline.gates import GateStatus
from enterprise_agent.pipeline.orchestrator import GateRejectedError, Orchestrator
from enterprise_agent.pipeline.state import PipelineState, PipelineStatus
from enterprise_agent.pipeline.store import RunStore

WEB_UI_TOKEN_ENV = "ENTERPRISE_AGENT_WEB_UI_TOKEN"


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _require_token(request: Request) -> None:
    expected = os.environ.get(WEB_UI_TOKEN_ENV)
    if not expected:
        return  # auth disabled -- local/dev only, see module docstring
    provided = request.query_params.get("token") or request.headers.get("x-auth-token")
    if provided != expected:
        raise HTTPException(status_code=401, detail="missing or invalid token")


def _page(title: str, body: str, token: str | None) -> HTMLResponse:
    token_qs = f"?token={html.escape(token)}" if token else ""
    return HTMLResponse(
        f"<!doctype html><html><head><title>{_esc(title)}</title></head>"
        f"<body style='font-family: sans-serif; max-width: 900px; margin: 2rem auto;'>"
        f"<p><a href='/{token_qs}'>&larr; all runs</a></p>"
        f"<h1>{_esc(title)}</h1>{body}</body></html>"
    )


def _run_row(state: PipelineState, token_qs: str) -> str:
    return (
        f"<tr><td><a href='/runs/{_esc(state.run_id)}{token_qs}'>{_esc(state.run_id)}</a></td>"
        f"<td>{_esc(state.status.value)}</td>"
        f"<td>{state.current_stage_index}/8</td>"
        f"<td>{_esc(state.updated_at)}</td></tr>"
    )


def _gate_history_html(state: PipelineState) -> str:
    if not state.gate_history:
        return "<p><em>no gate decisions yet</em></p>"
    rows = "".join(
        f"<tr><td>{_esc(g.stage)}</td><td>{_esc(g.status.value)}</td>"
        f"<td>{_esc(g.reviewer)}</td><td>{_esc(g.comment)}</td><td>{_esc(g.decided_at)}</td></tr>"
        for g in state.gate_history
    )
    return (
        "<table border='1' cellpadding='6'><tr><th>Stage</th><th>Decision</th>"
        f"<th>Reviewer</th><th>Comment</th><th>When</th></tr>{rows}</table>"
    )


def _artifacts_html(state: PipelineState) -> str:
    parts = []
    if state.intake_summary:
        parts.append(f"<h3>Intake summary</h3><pre>{_esc(state.intake_summary)}</pre>")
    if state.open_questions:
        items = "".join(f"<li>{_esc(q)}</li>" for q in state.open_questions)
        parts.append(f"<h3>Open questions</h3><ul>{items}</ul>")
    if state.brd:
        parts.append(f"<h3>BRD</h3><pre>{_esc(state.brd.content)}</pre>")
    if state.jira_refs:
        items = "".join(
            f"<li>{_esc(j.kind)} <a href='{_esc(j.url)}'>{_esc(j.key)}</a> - {_esc(j.title)}</li>"
            for j in state.jira_refs
        )
        parts.append(f"<h3>Jira</h3><ul>{items}</ul>")
    if state.tdd:
        parts.append(f"<h3>TDD (stack={_esc(state.tdd.stack)})</h3><pre>{_esc(state.tdd.content)}</pre>")
    if state.pr:
        parts.append(f"<h3>Pull request</h3><p><a href='{_esc(state.pr.url)}'>{_esc(state.pr.title)}</a></p>")
    if state.review_notes:
        items = "".join(
            f"<li>[{_esc(r.severity)}] {_esc(r.file)}: {_esc(r.comment)}</li>"
            for r in state.review_notes
        )
        parts.append(f"<h3>Review notes</h3><ul>{items}</ul>")
    if state.merge_result:
        parts.append(
            f"<h3>Merge result</h3><p>merged={_esc(state.merge_result.merged)} "
            f"sha={_esc(state.merge_result.commit_sha)}</p>"
        )
    if state.docs_links:
        items = "".join(f"<li><a href='{_esc(d.url)}'>{_esc(d.title)}</a></li>" for d in state.docs_links)
        parts.append(f"<h3>Docs</h3><ul>{items}</ul>")
    return "".join(parts)


def create_app(store: RunStore | None = None) -> FastAPI:
    orchestrator = Orchestrator(store=store or RunStore())
    app = FastAPI(title="Enterprise-Agent approval UI")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, _: None = Depends(_require_token)):
        token = request.query_params.get("token")
        token_qs = f"?token={html.escape(token)}" if token else ""
        run_ids = orchestrator.store.list_runs()
        rows = "".join(
            _run_row(orchestrator.store.load_state(run_id), token_qs) for run_id in run_ids
        )
        body = (
            "<table border='1' cellpadding='6'><tr><th>Run</th><th>Status</th>"
            f"<th>Stage</th><th>Updated</th></tr>{rows}</table>"
            if run_ids
            else "<p>No runs yet.</p>"
        )
        return _page("Runs", body, token)

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(run_id: str, request: Request, _: None = Depends(_require_token)):
        token = request.query_params.get("token")
        token_qs = f"?token={html.escape(token)}" if token else ""
        try:
            state = orchestrator.store.load_state(run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="run not found")

        body = f"<p>status: <b>{_esc(state.status.value)}</b> | stage: {state.current_stage_index}/8</p>"
        body += _artifacts_html(state)
        body += "<h3>Gate history</h3>" + _gate_history_html(state)

        if state.status is PipelineStatus.WAITING_FOR_APPROVAL:
            token_field = f"<input type='hidden' name='token' value='{_esc(token)}'>" if token else ""
            body += (
                "<h3>Decision needed</h3>"
                f"<form method='post' action='/runs/{_esc(run_id)}/decide{token_qs}'>"
                f"{token_field}"
                "<p>Reviewer: <input name='reviewer' required></p>"
                "<p>Comment: <input name='comment'></p>"
                "<p><button name='decision' value='approved'>Approve</button> "
                "<button name='decision' value='rejected'>Reject</button></p>"
                "</form>"
            )
        return _page(f"Run {run_id}", body, token)

    @app.post("/runs/{run_id}/decide")
    def decide(
        run_id: str,
        request: Request,
        decision: str = Form(...),
        reviewer: str = Form(...),
        comment: str = Form(""),
        _: None = Depends(_require_token),
    ):
        status = GateStatus.APPROVED if decision == "approved" else GateStatus.REJECTED
        try:
            orchestrator.resume(run_id, status, reviewer=reviewer, comment=comment or None)
        except (FileNotFoundError, GateRejectedError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RealModeError as e:
            # Run is unchanged (see orchestrator._run_until_blocked -- state
            # is only saved after a stage succeeds), safe to retry once the
            # underlying issue (credentials, network, ...) is fixed.
            raise HTTPException(status_code=502, detail=str(e))
        token = request.query_params.get("token")
        token_qs = f"?token={html.escape(token)}" if token else ""
        return RedirectResponse(url=f"/runs/{run_id}{token_qs}", status_code=303)

    return app
