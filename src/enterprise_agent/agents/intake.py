"""Stage 1: ingest a transcript/meeting notes -> summary + open questions.

This is the template the other 7 stages follow: declare `name`,
`requires_gate`, and `connectors`; pull inputs from `state` and `ctx`, wrap
any externally-sourced text in UntrustedContent before using it, write new
artifacts back onto `state`.
"""

from __future__ import annotations

from enterprise_agent.pipeline.stage import Stage, StageContext
from enterprise_agent.pipeline.state import PipelineState
from enterprise_agent.security.guardrails import UntrustedContent


class IntakeAgent(Stage):
    name = "intake"
    requires_gate = True
    connectors = ("otter",)

    def run(self, state: PipelineState, ctx: StageContext) -> PipelineState:
        otter = ctx.connectors["otter"]
        transcript = otter.get_transcript(meeting_id=state.run_id)
        untrusted = UntrustedContent(text=transcript.text, source="otter")
        raw_text = untrusted.as_prompt_data()

        state.transcript = raw_text
        state.intake_summary = (
            "Summary (stub): stakeholders discussed a new feature request; "
            "see transcript for full detail."
        )
        state.open_questions = [
            "What's the rate limit on reset requests?",
            "Do SSO users need a distinct flow?",
        ]
        state.touch()
        return state
