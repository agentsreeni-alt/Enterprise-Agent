# Synthetic test transcripts

Five realistic meeting-transcript scenarios for exercising the pipeline
end-to-end without waiting on real recordings. Each is a distinct change
type so stub-mode and `llm_mode="real"` output can be compared meaningfully
across runs instead of collapsing to one canned scenario.

| File | Scenario |
|---|---|
| `01-feature-password-reset.txt` | New feature, has an explicit open question (IP-based rate limiting) |
| `02-bugfix-checkout-timeout.txt` | Incident-driven bug fix, has an unresolved SLA question |
| `03-compliance-pii-audit-trail.txt` | Compliance/audit-driven change, retention + scope questions |
| `04-feature-finance-billing-export.txt` | Cross-functional feature request with a dependency on another workstream |
| `05-security-api-rate-limiting.txt` | Security incident response, phased-rollout judgment call |

## Usage

```bash
python -m enterprise_agent run --input testdata/transcripts/01-feature-password-reset.txt
python -m enterprise_agent approve --run-id <id> --reviewer <you> --comment "lgtm"
# repeat approve through BRD, TDD, Review, Merge gates
```

Or via the web UI (`python -m enterprise_agent serve`) once a run has
started from the CLI — both front doors operate on the same run state.

In mock/stub mode (the default), `intake_summary`/`open_questions`/BRD/TDD
content is deterministic canned text regardless of which transcript you
use — only the `transcript` field itself and connector-touching stages
(Jira/GitHub/Confluence, when in real mode) reflect the actual input. Set
`llm_mode="real"` on the `Orchestrator` to see these five scenarios
actually produce different generated content.
