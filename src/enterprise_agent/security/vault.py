"""Secrets vault (control #2) and the least-privilege scoping it enables
(control #1, enforced by pipeline/stage.py via each Stage's declared
`connectors` tuple).

Scaffold implementation: in-memory fake tokens with a short TTL. No real
Vault/AWS Secrets Manager call is made. The one invariant that must survive
the eventual swap-in: callers only ever get `ScopedToken.value` — nothing
that logs or persists a ScopedToken should ever include that field, only
`scope` and `expires_at`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DEFAULT_TTL = timedelta(minutes=5)


@dataclass
class ScopedToken:
    value: str
    scope: str
    expires_at: str

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > datetime.fromisoformat(self.expires_at)

    def redacted(self) -> dict:
        """Safe-to-log view: never includes `value`."""
        return {"scope": self.scope, "expires_at": self.expires_at}


class SecretsVault:
    """Issues short-lived, connector-scoped fake tokens. Real deployments would
    back this with Vault/AWS Secrets Manager; this scaffold never touches disk
    or the network for a secret.
    """

    def get_token(self, connector: str, ttl: timedelta = DEFAULT_TTL) -> ScopedToken:
        expires_at = (datetime.now(timezone.utc) + ttl).isoformat()
        return ScopedToken(
            value=f"mock-token-{connector}-{uuid.uuid4().hex[:8]}",
            scope=connector,
            expires_at=expires_at,
        )
