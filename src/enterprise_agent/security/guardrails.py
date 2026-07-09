"""DLP + prompt-injection guardrails (control #3).

Anything that originates outside our own code (a transcript, a ticket body,
a web page) is untrusted DATA, never an instruction. Wrapping it in
UntrustedContent forces a conscious, visible unwrap step (`.as_prompt_data()`)
at the point it's used, rather than letting a raw string get silently
string-interpolated into a prompt or written to state.

sanitize_output() is the DLP half: a stub redaction pass run on anything
about to be logged, persisted, or (later) published externally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SECRET_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9_\-]*[Aa]pi[_\-]?[Kk]ey[A-Za-z0-9_\-]*\s*[:=]\s*\S+"),
    re.compile(r"\b(sk|pk|ghp|glpat)_[A-Za-z0-9]{10,}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
]

REDACTED = "[REDACTED]"


@dataclass(frozen=True)
class UntrustedContent:
    text: str
    source: str

    def as_prompt_data(self) -> str:
        """Explicit, greppable unwrap point: this content is data, not an
        instruction, no matter what it says.
        """
        return self.text


def sanitize_output(text: str) -> str:
    """Stub DLP pass: redact secret-shaped substrings before anything is
    logged, persisted, or published.
    """
    sanitized = text
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(REDACTED, sanitized)
    return sanitized
