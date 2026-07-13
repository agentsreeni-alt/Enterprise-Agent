# Project Plan

Tracks the gap between the current scaffold and a pipeline that does real
work. Source of truth for "what's left" — update the checkboxes as phases
land instead of letting README's "Not yet implemented" section drift out of
sync.

See `docs/sales-readiness-dossier.html` for the executive-facing version of
this assessment (architecture diagram, real-vs-stub matrix, platform gaps,
pros/cons) — a point-in-time snapshot, not auto-updated as this file
changes.

## Current state (as of this plan)

- Orchestrator, gates, state persistence, CLI: real, not stubbed.
- Security foundation: real *logic*, scaffold *backends* (in-memory vault,
  bookkeeping-only sandbox, local JSONL audit log, flag-file kill switch).
- Jira connector: real (`connectors/atlassian_mcp.py`, via Atlassian's
  hosted MCP server). Every other connector (Otter, GitHub, Confluence) is
  mock-only.
- All 8 stages produce deterministic stub content (no LLM calls anywhere
  yet).

## Phases

Ordered by dependency + cost, not by importance — each phase reuses
infrastructure the previous one built where possible.

### Phase 1 — Real Confluence connector ✅
Extends `connectors/atlassian_mcp.py` (Confluence lives on the same
Atlassian remote MCP server as Jira, same env vars/auth already wired).
Unblocks the Docs stage.
- [x] `AtlassianMcpConfluenceConnector.publish_page`
- [x] Wire into `connectors/registry.py` real mode
- [x] Update README + `.env.example` if new env vars are needed

### Phase 2 — Real GitHub connector ✅
New module, same pattern as Atlassian: hosted MCP server + PAT env vars.
Unblocks Dev/Review/Merge running against a real repo.
- [x] `connectors/github_mcp.py`: `open_pull_request`, `request_changes`,
      `merge_pull_request`
- [x] Env vars + README section (mirroring the Jira one)
- [x] Wire into `connectors/registry.py` real mode
- Known limitation carried forward to Phase 3: `open_pull_request` commits
  the Dev stage's stub diff *text* to a marker file rather than applying
  real code changes, since Dev doesn't generate real diffs yet.

### Phase 3 — LLM-driven stage content ✅
Replace canned strings in Intake/BRD/TDD/Review with real
`claude-agent-sdk` calls, now that Jira/GitHub/Confluence can receive real
content instead of stub text.
- [x] Intake: real summarization + open-question extraction from transcript
- [x] BRD: real document generation from intake summary
- [x] TDD: real stack-aware technical design from BRD
- [x] Review: real diff-vs-TDD analysis instead of canned comment

Implementation notes:
- New `llm.py` module wraps `claude_agent_sdk.query` for plain
  text/JSON-generation calls (no tools/MCP servers -- these aren't agentic,
  just generation). Only imported inside each stage's real-mode branch, so
  stub mode (the default, all tests) never depends on it.
- `StageContext.llm_mode` ("stub" default / "real") and
  `Orchestrator(llm_mode=..., llm_mode_overrides=...)` mirror the existing
  `connector_mode`/`connector_mode_overrides` pattern exactly.
- Fixed a real gap surfaced while wiring Review: `DevAgent` generated a diff
  but never persisted it onto `PipelineState` (`dev_diff` field added), so
  Review had nothing to actually review. Not itself an LLM change, but
  Review's stated job ("diff the PR against the TDD") was structurally
  impossible without it.

### Phase 4 — Real transcript source ✅
No hosted MCP server for Otter, and no well-documented public API for
third-party transcript retrieval from Otter.ai itself -- generalized into
`connectors/notetaker.py` with two concrete backends behind the same
connector interface, selected by `ENTERPRISE_AGENT_TRANSCRIPT_SOURCE`:
- [x] `zoom`: real Zoom Cloud Recording REST API (Server-to-Server OAuth)
- [x] `webhook`: generic HTTP+API-key escape hatch for Otter/Fireflies/tl;dv/
      an internal relay -- anything reachable over HTTP
- [x] Env vars + README section
- [x] Wire into `connectors/registry.py` real mode

Not yet scheduled: real Dev-stage code generation (currently a deterministic
diff-string stub -- see the "Known limitation" note in
`connectors/github_mcp.py` and the README's Real GitHub section).

### Phase 5 — Security hardening ✅
- [x] Real secrets vault backend: pluggable `VaultBackend`
      (`HashiCorpVaultBackend` real KV v2 HTTP client, `EnvVaultBackend`
      fallback) behind the existing `SecretsVault` interface
- [x] Real sandbox settings: `SandboxPolicy.as_sandbox_settings()` produces
      a real `claude_agent_sdk.types.SandboxSettings` -- enforced once
      Dev/Review drive a real agentic loop (they don't yet; see below)
- [x] Durable audit storage: optional SQLite dual-write alongside the
      existing JSONL file, via `ENTERPRISE_AGENT_AUDIT_DB`

Not yet scheduled: real Dev-stage code generation is the remaining
prerequisite for the sandbox settings above to have a live, enforced
consumer (currently just a real, correctly-shaped config object with
nothing calling it inside a tool-using agent loop).

### Phase 6 — Web approval UI ✅
- [x] FastAPI app (`web/app.py`, optional `[web]` extra): list runs, view
      artifacts + gate history, approve/reject through the same
      `Orchestrator.resume()` path the CLI uses
- [x] `python -m enterprise_agent serve` CLI subcommand (lazy import, base
      install/tests never require fastapi/uvicorn)
- [x] Shared-token auth (`ENTERPRISE_AGENT_WEB_UI_TOKEN`)

Known limitation, stated rather than glossed over: auth is a single shared
token, not per-user identity/SSO. Fine as a stopgap; real multi-reviewer
deployments need real auth -- not yet scheduled as its own phase.

### Phase 7 — Real anomaly detection ✅
Automated triggers for `KillSwitch.trigger()` instead of manual-only:
- [x] `security/anomaly.py`: `DurationAnomalyDetector` flags a stage as an
      outlier vs. its historical mean/stdev (from the durable SQLite audit
      store), wired into the orchestrator between every stage
- [x] `security/guardrails.count_redactions()` + `StageContext.kill_switch`:
      Docs stage trips the kill switch immediately on any DLP hit before
      publishing to Confluence

## All 7 phases complete

Every phase above is done: real Jira/Confluence/GitHub/transcript-source
connectors, real LLM-driven stage content, a hardened security foundation
(real vault backend, real sandbox settings, durable audit), a web approval
UI, and automated anomaly detection. Remaining known limitations, all
called out where they live rather than hidden:
- Dev-stage code generation is still a deterministic diff-string stub
  (`agents/dev.py`, `connectors/github_mcp.py`'s docstring) -- the
  sandbox settings from Phase 5 have no live consumer until this lands.
- Web UI auth is a single shared token, not per-user identity/SSO
  (`web/app.py`'s docstring).
- Real anomaly detection above only covers duration outliers + DLP hits;
  it is not a general-purpose anomaly system.

Any of these three are reasonable next phases if this roadmap continues.

## Bugs found and fixed during pilot-testing prep

Not roadmap phases -- real defects found while getting ready to run the
pipeline against a real Jira/GitHub for the first time, fixed immediately
rather than logged for later:

- **Intake discarded the caller-supplied transcript.** `Orchestrator.start(text)`
  set `state.transcript`, but `IntakeAgent` unconditionally overwrote it by
  fetching from the otter connector -- so `run --input file.txt` had no
  effect on pipeline input; every run used identical connector-fetched
  text. Fixed: Intake now honors an already-supplied transcript and only
  falls back to the connector when none was given.
- **Connector/LLM mode wasn't persisted per-run.** A CLI-driven run always
  spans multiple processes (`run`, then a later `approve`), each
  constructing its own `Orchestrator()`. Mode lived only on that in-memory
  instance, so a run started with `--real jira` could silently fall back
  to mock on its next gate if the next CLI invocation didn't repeat the
  flag. Fixed: `RunStore.save_config`/`load_config` persist the mode a run
  was started with; `resume()` always reloads it. Also exposed `--real`
  and `--llm-real` on the CLI's `run` command -- previously the only way
  to invoke real mode at all was writing a Python script.
- **Real-mode connector failures surfaced as raw Python tracebacks.** A
  blocked-network real-Jira call crashed the CLI with a full stack trace
  instead of a clean message. Fixed: `errors.py`'s `RealModeError` is now
  the common base for every real-mode exception (Atlassian, GitHub,
  notetaker, LLM output parsing); the CLI and web UI catch it and print/
  return a one-line, actionable error instead.

## Live pilot-testing findings (this environment)

Attempted a real end-to-end run against a real Atlassian site with valid
credentials already configured. Intake and BRD ran correctly (including the
transcript-bug fix above); the Jira stage failed. Root cause, confirmed via
this session's own network proxy status endpoint rather than guessed: **this
Claude Code environment's egress policy blocks outbound HTTPS to
`mcp.atlassian.com` and `api.githubcopilot.com`** (both returned 403 at the
CONNECT level) -- i.e. it blocks third-party MCP server hosts in general,
not something specific to Jira. `github.com` itself (plain git operations)
is allowed; the separate MCP API host is not.

This is an environment/network-policy constraint, not a code defect --
config construction, auth header building, and the MCP tool allowlists were
all confirmed correct up to the point of the network call. To actually
complete a live test:
- Adjust this environment's network policy (claude.ai environment settings)
  to allow `mcp.atlassian.com` and `api.githubcopilot.com`, or
- Run the same `--real jira,confluence,github` flags from an environment
  without that restriction (a local machine, a CI runner, or a
  differently-configured Claude Code environment).

The failed run left no partial state and created nothing on the real Jira
site -- `RunStore` only saves state after a stage succeeds, so the run
parked safely at the BRD gate and is resumable once the network path is
open.

## Working agreement

- One phase (or one checkbox within a phase) at a time; commit + push after
  each, don't batch unrelated phases into one commit.
- Every new real connector follows the Jira precedent: mock mode stays the
  default, tests never import SDK/network code, real mode is opt-in via
  `connector_mode_overrides`.
- Update this file's checkboxes as work lands.
