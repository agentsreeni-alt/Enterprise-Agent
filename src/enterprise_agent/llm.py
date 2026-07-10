"""Real LLM-driven stage content via claude-agent-sdk.

Only imported when a stage's `ctx.llm_mode == "real"` -- kept out of the
import path entirely for "stub" mode (the default; all tests, CI) so no
stage carries an SDK/network dependency unless explicitly opted in. Mirrors
how connectors/atlassian_mcp.py and connectors/github_mcp.py are only
loaded in real connector mode.

No tools/MCP servers are attached here -- these are plain text-generation
calls, not agentic tool use, so there's no allowlist to declare.
"""

from __future__ import annotations

import asyncio
import json
import re

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query


async def _aprompt(prompt: str, system_prompt: str | None = None) -> str:
    options = ClaudeAgentOptions(tools=[])
    if system_prompt:
        options.system_prompt = system_prompt
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
    return "".join(chunks)


def run_prompt(prompt: str, system_prompt: str | None = None) -> str:
    """Synchronous wrapper -- stages are synchronous, same convention as
    every connector's asyncio.run(...) call.
    """
    return asyncio.run(_aprompt(prompt, system_prompt))


class LLMOutputError(ValueError):
    """Raised when a stage's response never contains the JSON it asked for."""


def parse_json(text: str):
    """Best-effort extraction of a JSON object/array from LLM output that
    may be wrapped in prose or a ```json fence.
    """
    match = re.search(r"[\{\[].*[\}\]]", text, re.DOTALL)
    if not match:
        raise LLMOutputError(f"no JSON value found in LLM output: {text!r}")
    return json.loads(match.group(0))
