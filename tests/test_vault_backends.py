"""Tests for the pluggable VaultBackend behind SecretsVault. No real Vault
server is contacted -- HashiCorpVaultBackend's HTTP call is monkeypatched.
"""

from __future__ import annotations

import json

from enterprise_agent.security.vault import (
    EnvVaultBackend,
    HashiCorpVaultBackend,
    SecretsVault,
    VAULT_ADDR_ENV,
    VAULT_TOKEN_ENV,
    build_vault_backend_from_env,
)


def test_env_backend_reads_configured_secret(monkeypatch):
    monkeypatch.setenv("ENTERPRISE_AGENT_SECRET_JIRA", "real-jira-secret")
    backend = EnvVaultBackend()
    assert backend.get_secret("jira") == "real-jira-secret"


def test_env_backend_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("ENTERPRISE_AGENT_SECRET_GITHUB", raising=False)
    backend = EnvVaultBackend()
    assert backend.get_secret("github") is None


def test_secrets_vault_uses_backend_secret_when_present(monkeypatch):
    monkeypatch.setenv("ENTERPRISE_AGENT_SECRET_JIRA", "real-jira-secret")
    token = SecretsVault(backend=EnvVaultBackend()).get_token("jira")
    assert token.value == "real-jira-secret"
    assert token.scope == "jira"


def test_secrets_vault_falls_back_to_fake_token_when_backend_has_nothing(monkeypatch):
    monkeypatch.delenv("ENTERPRISE_AGENT_SECRET_JIRA", raising=False)
    token = SecretsVault(backend=EnvVaultBackend()).get_token("jira")
    assert token.value.startswith("mock-token-jira-")


def test_build_vault_backend_from_env_defaults_to_env_backend(monkeypatch):
    monkeypatch.delenv(VAULT_ADDR_ENV, raising=False)
    monkeypatch.delenv(VAULT_TOKEN_ENV, raising=False)
    assert isinstance(build_vault_backend_from_env(), EnvVaultBackend)


def test_build_vault_backend_from_env_picks_hashicorp_when_configured(monkeypatch):
    monkeypatch.setenv(VAULT_ADDR_ENV, "https://vault.example.com")
    monkeypatch.setenv(VAULT_TOKEN_ENV, "root-token")
    backend = build_vault_backend_from_env()
    assert isinstance(backend, HashiCorpVaultBackend)
    assert backend.addr == "https://vault.example.com"
    assert backend.token == "root-token"


class _FakeHttpResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_hashicorp_backend_parses_kv_v2_response(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=None: _FakeHttpResponse(
            {"data": {"data": {"value": "vault-secret"}}}
        ),
    )
    backend = HashiCorpVaultBackend(addr="https://vault.example.com", token="t")
    assert backend.get_secret("jira") == "vault-secret"
