"""M3 — policy engine tests: the user controls what gets protected and how."""
import json
from pathlib import Path

import exodus.policy.policy as policy_mod
from exodus.classify.sensitivity import Sensitivity
from exodus.policy.policy import Action, Policy
from exodus.transform.pipeline import sanitize_request_body

_SECRET = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA1111"


def _body(text: str) -> bytes:
    return json.dumps({"model": "m", "messages": [{"role": "user", "content": text}]}).encode()


def test_default_masks_secret_but_forwards_email():
    out, _vault, applied = sanitize_request_body(_body(f"key {_SECRET} mail a@b.com"))
    s = out.decode()
    assert "⟪EXODUS:anthropic_key:" in s          # secret pseudonymized
    assert "a@b.com" in s                          # email forwarded (default PUBLIC)
    assert ("anthropic_key", "pseudonymize") in applied


def test_user_can_enable_email_protection():
    pol = Policy.default()
    pol.kind_tiers["email"] = Sensitivity.LOW       # LOW -> pseudonymize
    out, _vault, applied = sanitize_request_body(_body("mail a@b.com"), pol)
    s = out.decode()
    assert "a@b.com" not in s
    assert "⟪EXODUS:email:" in s
    assert ("email", "pseudonymize") in applied


def test_block_action_is_non_reversible():
    pol = Policy.default()
    pol.tier_actions[Sensitivity.SECRET] = Action.BLOCK   # redact instead of mask
    out, vault, applied = sanitize_request_body(_body(f"key {_SECRET}"), pol)
    s = out.decode()
    assert "[EXODUS-BLOCKED:anthropic_key]" in s
    assert _SECRET not in s
    assert len(vault) == 0                          # nothing stored -> cannot be restored
    assert ("anthropic_key", "block") in applied


def test_from_yaml_parses_tiers_and_kinds(tmp_path):
    # Use a controlled YAML, NOT the user-editable example file.
    p = tmp_path / "policy.yaml"
    p.write_text(
        "kinds:\n"
        "  email: LOW\n"
        "  github_token: PUBLIC\n"
        "tiers:\n"
        "  SECRET: block\n"
        "  LOW: pseudonymize\n"
        "  PUBLIC: forward\n"
    )
    pol = Policy.from_yaml(str(p))
    assert pol.action_for_kind("email") == Action.PSEUDONYMIZE      # LOW -> pseudonymize
    assert pol.action_for_kind("github_token") == Action.FORWARD    # PUBLIC -> forward
    assert pol.action_for_kind("anthropic_key") == Action.BLOCK     # default SECRET tier, here -> block
    assert pol.action_for_kind("unknown") == Action.BLOCK           # fail-closed (treated as SECRET)


def test_example_yaml_is_loadable():
    # The shipped example must always parse, whatever PII tweaks the user made,
    # and secrets must still be protected (pseudonymize or block — never forward).
    example = Path(policy_mod.__file__).parent / "policy.example.yaml"
    pol = Policy.from_yaml(str(example))
    assert pol.action_for_kind("anthropic_key") in {Action.PSEUDONYMIZE, Action.BLOCK}
