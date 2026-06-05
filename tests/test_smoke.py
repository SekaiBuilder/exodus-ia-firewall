"""Smoke tests + leak-canary scaffold.

These run with no network and no local model. They assert the package imports and
that deterministic detectors catch obvious secrets/PII — the seed of invariant INV-1.
"""
from exodus.classify import detectors
from exodus.transform.pseudonymize import Vault


def test_package_imports():
    import exodus  # noqa: F401


def test_detects_anthropic_key():
    hits = detectors.scan("here is sk-ant-ABCDEFGHIJKLMNOPQRSTUV12345 ok")
    assert "anthropic_key" in {h.kind for h in hits}


def test_detects_email_and_ip():
    hits = detectors.scan("mail me at alice@example.com from 10.0.0.1")
    kinds = {h.kind for h in hits}
    assert "email" in kinds and "ipv4" in kinds


def test_vault_round_trips_exactly():
    """INV-3 seed: pseudonymize -> restore must reproduce the original value."""
    vault = Vault()
    token = vault.placeholder_for("super-secret-value", "api_key")
    assert token not in "super-secret-value"        # the placeholder is not the secret
    restored = vault.restore(f"use {token} please")
    assert restored == "use super-secret-value please"


# TODO(M2): canary test — assert no real SECRET value appears in the upstream payload.
