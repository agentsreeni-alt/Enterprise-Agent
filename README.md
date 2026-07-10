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

python -m enterprise_agent serve
# -> web approval UI at http://127.0.0.1:8000, requires `pip install -e ".[web]"`
```

Setting a kill-switch flag (`.enterprise_agent/KILLSWITCH`) aborts any run
before its next stage.

## Tests

```bash
pytest tests/
```

`tests/test_orchestrator_smoke.py` drives the entire pipeline end-to-end
against mocks only — no network, no credentials.

## Real Jira + Confluence (via Atlassian's remote MCP server)

The Jira and Confluence connectors both have real implementations in
`connectors/atlassian_mcp.py` (same hosted MCP server, same env vars), gated
behind `connector_mode_overrides={"jira": "real"}` and/or
`{"confluence": "real"}` on the `Orchestrator` (everything else stays
mocked). They talk to Atlassian's hosted MCP server
(`https://mcp.atlassian.com/v1/mcp`) instead of a hand-rolled REST client, so
no Jira/Confluence API token is ever embedded in this codebase.

Copy `.env.example` to `.env` and fill in the values below (then load it into
your shell however you prefer, e.g. `set -a && source .env && set +a` --
nothing in this repo reads `.env` automatically).

One-time manual setup (cannot be done from inside this repo/CI):

1. **Recommended — headless API token** (works in CI/cron/ephemeral
   environments): have an Atlassian org admin enable API token authentication
   under *Atlassian Administration → Rovo → Rovo MCP server → Authentication*,
   generate a fresh Jira API token, and set:
   - `ENTERPRISE_AGENT_ATLASSIAN_SITE_URL` (e.g. `https://yoursite.atlassian.net`)
   - `ENTERPRISE_AGENT_ATLASSIAN_EMAIL` + `ENTERPRISE_AGENT_ATLASSIAN_API_TOKEN`
     (or `ENTERPRISE_AGENT_ATLASSIAN_API_KEY` for a service-account key)

   Store these as env vars / secrets-manager entries only — never in code or git.

2. **Fallback — interactive OAuth** (no admin action needed, but manual
   per-machine): run `claude mcp add --transport http atlassian
   https://mcp.atlassian.com/v1/mcp` once on the machine that will run this
   pipeline and complete the browser consent screen. Then only
   `ENTERPRISE_AGENT_ATLASSIAN_SITE_URL` needs to be set — no token env vars.

Without `ENTERPRISE_AGENT_ATLASSIAN_SITE_URL` set, `get_connector("jira" | "confluence",
mode="real")` raises `AtlassianMcpConfigError` naming this setup step.
Mock mode is entirely unaffected and needs none of this.

## Real GitHub (via GitHub's remote MCP server)

The GitHub connector has a real implementation in `connectors/github_mcp.py`,
gated behind `connector_mode_overrides={"github": "real"}` on the
`Orchestrator` (everything else stays mocked). It talks to GitHub's hosted
MCP server instead of a hand-rolled REST client, so no GitHub token is ever
embedded in this codebase. Powers the Dev (opens PR), Review (posts review),
and Merge (merges PR) stages.

Set, via `.env.example`:
- `ENTERPRISE_AGENT_GITHUB_REPO` (`"owner/repo"`)
- `ENTERPRISE_AGENT_GITHUB_TOKEN` (fine-grained PAT scoped to that repo's
  contents + pull-requests permissions only)
- `ENTERPRISE_AGENT_GITHUB_BASE_BRANCH` (optional, defaults to `main`)

Store the token as an env var / secrets-manager entry only — never in code
or git. Without `ENTERPRISE_AGENT_GITHUB_REPO`/`_TOKEN` set,
`get_connector("github", mode="real")` raises `GitHubMcpConfigError` naming
this setup step. Mock mode is entirely unaffected and needs none of this.

**Known limitation:** the Dev stage is still a deterministic stub (real
code generation for Dev isn't scheduled as its own `PROJECT_PLAN.md` phase
yet) — it produces a plain diff *string*, not real code changes, and
GitHub's MCP tool set has no "apply unified diff" primitive. Until Dev
generates real changes, `open_pull_request` commits that diff text
verbatim to a marker file so the PR has a real, reviewable commit against
base, rather than applying it as actual code.

## Real transcript source (Intake stage)

The "otter" connector isn't a single-vendor Otter.ai client -- Otter has no
well-documented public API for third-party transcript retrieval, and
companies use all kinds of note-takers. `connectors/notetaker.py` instead
implements two concrete backends behind the same connector interface,
gated behind `connector_mode_overrides={"otter": "real"}`, selected by
`ENTERPRISE_AGENT_TRANSCRIPT_SOURCE`:

- **`zoom`** — Zoom's real Cloud Recording REST API via a Server-to-Server
  OAuth app (create one in Zoom App Marketplace). Set
  `ENTERPRISE_AGENT_ZOOM_ACCOUNT_ID`, `ENTERPRISE_AGENT_ZOOM_CLIENT_ID`,
  `ENTERPRISE_AGENT_ZOOM_CLIENT_SECRET`.
- **`webhook`** — a generic HTTP+API-key escape hatch for whatever your
  actual note-taker (Otter, Fireflies, tl;dv, an internal relay, ...)
  exposes. Set `ENTERPRISE_AGENT_TRANSCRIPT_WEBHOOK_URL` (a template
  containing `{meeting_id}`) and, if the endpoint needs one,
  `ENTERPRISE_AGENT_TRANSCRIPT_WEBHOOK_API_KEY` (sent as a Bearer token).

Without `ENTERPRISE_AGENT_TRANSCRIPT_SOURCE` set to a recognized value,
`get_connector("otter", mode="real")` raises `NotetakerConfigError` naming
this setup step. Mock mode is entirely unaffected and needs none of this.

## Real LLM-driven stage content

Intake, BRD, TDD, and Review can generate real content via
`claude-agent-sdk` instead of their deterministic stub strings, gated
behind `llm_mode="real"` (and/or per-stage `llm_mode_overrides={"brd": "real"}`)
on the `Orchestrator` -- same pattern as `connector_mode`/
`connector_mode_overrides`. Defaults to `llm_mode="stub"`, so existing
behavior (and every test) is unaffected unless a run opts in.

## Security hardening (vault, sandbox, durable audit)

- **Secrets vault**: `SecretsVault` now reads real secrets from a pluggable
  `VaultBackend` -- a real HashiCorp Vault server (KV v2 API) when
  `ENTERPRISE_AGENT_VAULT_ADDR` + `ENTERPRISE_AGENT_VAULT_TOKEN` are set, or
  `ENTERPRISE_AGENT_SECRET_<CONNECTOR>` env vars otherwise. Falls back to a
  synthesized dev-mode token when neither is configured for a connector, so
  existing mock-mode behavior is unchanged.
- **Sandbox**: `SandboxPolicy.as_sandbox_settings()` produces a real
  `claude_agent_sdk.types.SandboxSettings` (bash-command filesystem/network
  isolation, mapping `no_network_to` to `deniedDomains`). This becomes
  genuinely enforced once Dev/Review actually drive an agentic
  `claude_agent_sdk.query()` loop with tool access -- which they don't yet
  (see "Not yet implemented" below) -- so today it's a real, usable config
  object without a live consumer.
- **Durable audit**: set `ENTERPRISE_AGENT_AUDIT_DB` to also write every
  audit record to a SQLite database (in addition to, not instead of, the
  per-run `audit.log` JSONL file).

## Web approval UI

`python -m enterprise_agent serve` (requires `pip install -e ".[web]"`)
runs a small FastAPI app that lists runs, shows each run's artifacts and
gate history, and lets a reviewer approve/reject directly from the
browser -- through the exact same `Orchestrator.resume()` path the CLI
uses, so gate semantics are identical either way. Options:
- `--host` / `--port` (default `127.0.0.1:8000`)

Set `ENTERPRISE_AGENT_WEB_UI_TOKEN` to require a shared token on every
request (`?token=...` in the URL). **Known limitation:** this is a single
shared secret, not per-user identity/SSO -- fine as a stopgap, not a
substitute for real auth in a multi-reviewer deployment (see
`PROJECT_PLAN.md`). Leaving it unset disables auth entirely -- local/dev
use on localhost only.

## Real anomaly detection

Two automated, independent triggers for `KillSwitch.trigger()` -- no
human has to notice something is wrong and flip the switch manually:

- **Stage duration outliers**: with `ENTERPRISE_AGENT_AUDIT_DB` set (see
  above), the orchestrator compares each completed stage's wall-clock
  duration against that stage's historical mean/stdev and trips the kill
  switch if it's a statistical outlier. Needs at least 3 prior runs of
  history for a stage before it'll flag anything.
- **DLP redactions**: the Docs stage scans BRD/TDD content with
  `security.guardrails.count_redactions()` before publishing to
  Confluence; any secret-shaped substring found trips the kill switch
  immediately (via the new `StageContext.kill_switch`).

Same limitation as every kill-switch check: it interrupts the orchestrator
*between* stages, not a stage's own execution mid-call (see
`security/kill_switch.py`).

## Not yet implemented

See `PROJECT_PLAN.md` for the phased roadmap. In short: real Dev-stage code
generation (needed before the sandbox settings above have a live
consumer) and real per-user auth for the web UI.
