# Enterprise-Agent

Requirements-to-Reviewable-PR agent pipeline. An orchestrator routes work through
8 subagents that turn a meeting transcript into a merged, human-reviewed pull
request — then stops. It never touches production deployment. See
`architecture-diagram.svg` for the full design.

## Status

This is the pipeline **scaffold**: all 8 stages run as deterministic stubs
against mocked connectors (Jira/GitHub/Confluence/Otter), wired through a real
orchestrator with real human-approval gates and a working security foundation
(least privilege, secrets vault, guardrails, sandboxing, audit log, kill
switch). No stage is LLM-driven yet, and no real external API is called.

## Pipeline stages

| # | Stage | Gate? |
|---|-------|:---:|
| 1 | Intake — transcript → summary + open questions | ✅ |
| 2 | BRD — business requirements doc | ✅ |
| 3 | Jira — epics/stories linked to the BRD | — |
| 4 | TDD — stack-aware technical design | ✅ |
| 5 | Dev — implements in a sandbox, opens a PR only | — |
| 6 | Review — diffs PR vs. TDD + standards | ✅ |
| 7 | Merge — merges the approved PR. Pipeline ends here. | ✅ |
| 8 | Docs — publishes BRD/TDD to Confluence | — |

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
python -m enterprise_agent run --input transcript.txt
# -> pauses at the Intake gate, prints a run_id

python -m enterprise_agent approve --run-id <id> --reviewer alice --comment "lgtm"
# -> repeat through BRD, TDD, Review, and Merge gates to reach status=completed

python -m enterprise_agent reject --run-id <id> --reviewer alice --comment "not ready"
# -> halts the run permanently

python -m enterprise_agent status --run-id <id>
python -m enterprise_agent list-runs
```

Setting a kill-switch flag (`.enterprise_agent/KILLSWITCH`) aborts any run
before its next stage.

## Tests

```bash
pytest tests/
```

`tests/test_orchestrator_smoke.py` drives the entire pipeline end-to-end
against mocks only — no network, no credentials.

## Not yet implemented

Real `claude_agent_sdk`-driven stage intelligence, real Jira/GitHub/Confluence/Otter
clients, real secrets vault, real sandboxing/container isolation, durable audit
storage beyond a local JSONL file, a web approval UI, and real anomaly detection.
