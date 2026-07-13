"""CLI entry point: run / approve / reject / status / list-runs.

Gates are real pause points: `run` and `approve` return control to the shell
as soon as a gated stage completes. A later, separate invocation of
`approve`/`reject` is the only way to continue -- there's no in-process
callback to survive.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from enterprise_agent.errors import RealModeError
from enterprise_agent.pipeline.gates import GateStatus
from enterprise_agent.pipeline.orchestrator import GateRejectedError, Orchestrator
from enterprise_agent.pipeline.state import PipelineState


def _print_state_summary(state: PipelineState) -> None:
    print(f"run_id:        {state.run_id}")
    print(f"status:        {state.status.value}")
    print(f"current_stage: {state.current_stage_index}/8")
    if state.open_questions:
        print(f"open_questions: {state.open_questions}")
    if state.brd:
        print(f"brd:           set (template={state.brd.template})")
    if state.jira_refs:
        print(f"jira_refs:     {[j.key for j in state.jira_refs]}")
    if state.tdd:
        print(f"tdd:           set (stack={state.tdd.stack})")
    if state.pr:
        print(f"pr:            {state.pr.id} ({state.pr.url})")
    if state.review_notes:
        print(f"review_notes:  {len(state.review_notes)} comment(s)")
    if state.merge_result:
        print(f"merge_result:  merged={state.merge_result.merged} sha={state.merge_result.commit_sha}")
    if state.docs_links:
        print(f"docs_links:    {[d.url for d in state.docs_links]}")
    if state.gate_history:
        print("gate_history:")
        for g in state.gate_history:
            print(f"  - {g.stage}: {g.status.value} (reviewer={g.reviewer}, comment={g.comment!r})")


def cmd_run(args: argparse.Namespace) -> int:
    transcript_text = Path(args.input).read_text()
    real_kinds = [k.strip() for k in args.real.split(",")] if args.real else []
    orch = Orchestrator(
        connector_mode_overrides={k: "real" for k in real_kinds},
        llm_mode="real" if args.llm_real else "stub",
    )
    try:
        state = orch.start(transcript_text)
    except RealModeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _print_state_summary(state)
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    orch = Orchestrator()
    try:
        state = orch.resume(
            args.run_id, GateStatus.APPROVED, reviewer=args.reviewer, comment=args.comment
        )
    except (FileNotFoundError, GateRejectedError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except RealModeError as e:
        print(f"error: {e}", file=sys.stderr)
        print(
            f"run_id {args.run_id} is unchanged -- fix the issue above and re-run "
            "`approve` with the same --run-id once it's resolved.",
            file=sys.stderr,
        )
        return 1
    _print_state_summary(state)
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    orch = Orchestrator()
    try:
        state = orch.resume(
            args.run_id, GateStatus.REJECTED, reviewer=args.reviewer, comment=args.comment
        )
    except (FileNotFoundError, GateRejectedError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _print_state_summary(state)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    orch = Orchestrator()
    try:
        state = orch.store.load_state(args.run_id)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _print_state_summary(state)
    return 0


def cmd_list_runs(args: argparse.Namespace) -> int:
    orch = Orchestrator()
    runs = orch.store.list_runs()
    if not runs:
        print("no runs found")
        return 0
    for run_id in runs:
        state = orch.store.load_state(run_id)
        print(f"{run_id}  status={state.status.value}  stage={state.current_stage_index}/8")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    # Lazy import: fastapi/uvicorn are an optional "web" extra, never
    # required for run/approve/reject/status/list-runs.
    import uvicorn

    from enterprise_agent.web.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="enterprise_agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Start a new pipeline run from a transcript file")
    p_run.add_argument("--input", required=True, help="Path to a transcript/notes text file")
    p_run.add_argument(
        "--real",
        default=None,
        help=(
            "Comma-separated connector kinds to run in real mode, e.g. "
            "'jira,confluence,github,otter'. Requires that connector's env "
            "vars to be set (see README.md/.env.example). Everything else "
            "stays mocked. This choice is persisted for the whole run -- "
            "later `approve`/`reject` calls automatically keep using it."
        ),
    )
    p_run.add_argument(
        "--llm-real",
        action="store_true",
        help="Generate real Intake/BRD/TDD/Review content via claude-agent-sdk instead of stub text.",
    )
    p_run.set_defaults(func=cmd_run)

    p_approve = sub.add_parser("approve", help="Approve the current gate and continue")
    p_approve.add_argument("--run-id", required=True)
    p_approve.add_argument("--reviewer", default=None)
    p_approve.add_argument("--comment", default=None)
    p_approve.set_defaults(func=cmd_approve)

    p_reject = sub.add_parser("reject", help="Reject the current gate, halting the run")
    p_reject.add_argument("--run-id", required=True)
    p_reject.add_argument("--reviewer", default=None)
    p_reject.add_argument("--comment", default=None)
    p_reject.set_defaults(func=cmd_reject)

    p_status = sub.add_parser("status", help="Show a run's current state")
    p_status.add_argument("--run-id", required=True)
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list-runs", help="List all runs and their status")
    p_list.set_defaults(func=cmd_list_runs)

    p_serve = sub.add_parser("serve", help="Run the web approval UI (requires the 'web' extra)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
