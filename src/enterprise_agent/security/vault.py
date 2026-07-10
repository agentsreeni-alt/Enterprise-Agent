"""Secrets vault (control #2) and the least-privilege scoping it enables
(control #1, enforced by pipeline/stage.py via each Stage's declared
`connectors` tuple).

`SecretsVault` issues short-lived, connector-scoped tokens. The value it
issues comes from a pluggable `VaultBackend`:

- `EnvVaultBackend` (default): reads a real operator-provided secret from
  an env var per connector. No external service required.
- `HashiCorpVaultBackend`: real HTTP calls to a Vault server's KV v2 API
  (stdlib `urllib` only, no new dependency).

If a backend has no secret configured for a connector, `get_token` falls
back to the original scaffold behavior (a synthesized fake token) -- this
keeps mock-mode runs and existing tests working unchanged, while giving
real deployments an actual place to plug in real secrets.

The one invariant that must survive any future backend swap: callers only
ever get `ScopedToken.value` -- nothing that logs or persists a ScopedToken
should ever include that field, only `scope` and `expires_at`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

DEFAULT_TTL = timedelta(minutes=5)

VAULT_ADDR_ENV = "ENTERPRISE_AGENT_VAULT_ADDR"
VAULT_TOKEN_ENV = "ENTERPRISE_AGENT_VAULT_TOKEN"
VAULT_KV_MOUNT_ENV = "ENTERPRISE_AGENT_VAULT_KV_MOUNT"
DEFAULT_KV_MOUNT = "secret"


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


class VaultBackend(Protocol):
    def get_secret(self, path: str) -> str | None: ...


@dataclass
class EnvVaultBackend:
    """Reads `ENTERPRISE_AGENT_SECRET_<PATH_UPPER>` from the environment.
    Real in the sense that it returns an actual operator-provided secret
    (not a fabricated value) -- just backed by env vars instead of a
    dedicated secrets service, for deployments that don't run one.
    """

    prefix: str = "ENTERPRISE_AGENT_SECRET_"

    def get_secret(self, path: str) -> str | None:
        env_name = self.prefix + path.upper().replace("-", "_").replace("/", "_")
        return os.environ.get(env_name)


@dataclass
class HashiCorpVaultBackend:
    """Real HTTP client for Vault's KV v2 secrets engine."""

    addr: str
    token: str
    kv_mount: str = DEFAULT_KV_MOUNT

    def get_secret(self, path: str) -> str | None:
        url = f"{self.addr.rstrip('/')}/v1/{self.kv_mount}/data/{path}"
        request = urllib.request.Request(
            url, headers={"X-Vault-Token": self.token}, method="GET"
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        data = body.get("data", {}).get("data", {})
        return data.get("value")


def build_vault_backend_from_env() -> VaultBackend:
    addr = os.environ.get(VAULT_ADDR_ENV)
    token = os.environ.get(VAULT_TOKEN_ENV)
    if addr and token:
        return HashiCorpVaultBackend(
            addr=addr, token=token, kv_mount=os.environ.get(VAULT_KV_MOUNT_ENV, DEFAULT_KV_MOUNT)
        )
    return EnvVaultBackend()


class SecretsVault:
    """Issues short-lived, connector-scoped tokens, backed by a real
    `VaultBackend` when one has a secret configured for that connector;
    otherwise falls back to a fake token (dev-mode scaffold behavior).
    """

    def __init__(self, backend: VaultBackend | None = None):
        self.backend = backend or EnvVaultBackend()

    def get_token(self, connector: str, ttl: timedelta = DEFAULT_TTL) -> ScopedToken:
        expires_at = (datetime.now(timezone.utc) + ttl).isoformat()
        real_secret = self.backend.get_secret(connector)
        value = real_secret if real_secret is not None else f"mock-token-{connector}-{uuid.uuid4().hex[:8]}"
        return ScopedToken(value=value, scope=connector, expires_at=expires_at)
