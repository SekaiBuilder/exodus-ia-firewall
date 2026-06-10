"""Request-body transformation pipeline.

Two passes run over the Anthropic Messages JSON before egress:

1. ``contextual_pass`` (optional) — local-model minimization of sensitive user prose
   (abstraction). One-way and lossy. Runs only when a runtime is provided.
2. ``sanitize_request_body`` — deterministic secret/PII firewall driven by policy
   (forward / pseudonymize / block). Reversible for pseudonymize.

In the proxy, pass 1 runs first (on raw prose), then pass 2 adds the reversible
placeholders — so response restoration only ever deals with pass 2's vault.
Non-JSON bodies pass through both untouched.
"""
from __future__ import annotations

import json

from exodus.classify import detectors
from exodus.classify.sensitivity import Sensitivity
from exodus.policy.policy import Action, Policy
from exodus.transform.local_pass import minimize_text
from exodus.transform.pseudonymize import Vault, apply_replacements, resolve_overlaps

_BLOCK_MARK = "[EXODUS-BLOCKED:{kind}]"


# ----------------------------------------------------------------------------------
# Pass 2 — deterministic firewall (policy-driven)
# ----------------------------------------------------------------------------------
def _transform(text: str, policy: Policy, vault: Vault, applied: list[tuple[str, str]]) -> str:
    chosen = resolve_overlaps(detectors.scan(text))
    repls: list[tuple[int, int, str]] = []
    for d in chosen:
        action = policy.action_for_kind(d.kind)
        if action == Action.PSEUDONYMIZE:
            repls.append((d.start, d.end, vault.placeholder_for(text[d.start : d.end], d.kind)))
            applied.append((d.kind, action.value))
        elif action == Action.BLOCK:
            repls.append((d.start, d.end, _BLOCK_MARK.format(kind=d.kind)))
            applied.append((d.kind, action.value))
        # Action.FORWARD -> leave the value untouched
    return apply_replacements(text, repls) if repls else text


def _walk(obj, policy: Policy, vault: Vault, applied: list[tuple[str, str]]):
    if isinstance(obj, str):
        return _transform(obj, policy, vault, applied)
    if isinstance(obj, list):
        return [_walk(x, policy, vault, applied) for x in obj]
    if isinstance(obj, dict):
        return {k: _walk(v, policy, vault, applied) for k, v in obj.items()}
    return obj


def sanitize_request_body(body: bytes, policy: Policy | None = None):
    """Return ``(sanitized_body, vault, applied)``. See module docstring."""
    policy = policy or Policy.default()
    vault = Vault()
    if not body:
        return body, vault, []
    try:
        obj = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body, vault, []

    applied: list[tuple[str, str]] = []
    sanitized = _walk(obj, policy, vault, applied)
    if not applied:
        return body, vault, []
    return json.dumps(sanitized, ensure_ascii=False).encode("utf-8"), vault, applied


# ----------------------------------------------------------------------------------
# Pass 1 — contextual minimization (local model, optional)
# ----------------------------------------------------------------------------------
def _min_content(content, runtime, min_tier: Sensitivity, statuses: list[str]):
    if isinstance(content, str):
        new, status = minimize_text(content, runtime, min_tier)
        statuses.append(status)
        return new
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                new, status = minimize_text(block["text"], runtime, min_tier)
                statuses.append(status)
                out.append({**block, "text": new})
            else:
                out.append(block)
        return out
    return content


def contextual_pass(body: bytes, runtime, min_tier: Sensitivity = Sensitivity.MEDIUM):
    """Abstract sensitive prose in user messages via the local model.

    Returns ``(new_body, statuses)``. Synchronous — wrap in a worker thread when
    calling from async code. Non-JSON/empty bodies pass through untouched.
    """
    if not body:
        return body, []
    try:
        obj = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body, []

    statuses: list[str] = []
    msgs = obj.get("messages") if isinstance(obj, dict) else None
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict) and m.get("role") == "user" and "content" in m:
                m["content"] = _min_content(m["content"], runtime, min_tier, statuses)

    changed = any(s.startswith(("abstracted", "blocked")) for s in statuses)
    if not changed:
        return body, statuses
    return json.dumps(obj, ensure_ascii=False).encode("utf-8"), statuses


def mask_text(text: str, policy: Policy | None = None):
    """Mask a plain-text string. Returns ``(masked, vault, applied)``.

    Same deterministic firewall as the proxy path, exposed for callers that
    hold text rather than a JSON request body (e.g. the MCP server).
    """
    policy = policy or Policy.default()
    vault = Vault()
    applied: list[tuple[str, str]] = []
    masked = _transform(text, policy, vault, applied)
    return masked, vault, applied
