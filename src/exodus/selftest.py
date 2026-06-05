"""Self-test: run a fake sample of every detector kind through the real pipeline.

Proves three things end to end, on synthetic data only (no real secrets):

  1. detection   - every supported kind is recognized,
  2. masking     - values the policy protects never appear in the egress body,
  3. restoration - the local vault rebuilds the original bytes exactly.

Run it with ``exodus selftest`` (or ``python -m exodus.selftest``). Every value
below is FAKE: documented test tokens, reserved-for-docs identifiers, or filler.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

from exodus.classify import detectors
from exodus.policy.policy import Policy
from exodus.transform.pipeline import sanitize_request_body
from exodus.transform.pseudonymize import StreamRestorer


def _pad(n: int, seed: str = "FAKEdemoEXODUS") -> str:
    """A deterministic, clearly-fake filler string of exactly ``n`` characters."""
    return (seed * (n // len(seed) + 1))[:n]


# One synthetic sample per detector kind. Documented test values (Stripe's 4242
# card, RFC-5737 example IP, the canonical example IBAN) or obvious filler. The
# DNI/NIE/SSN values are constructed to pass their check digit so the validators
# fire; none of this is a real credential.
SAMPLES: list[tuple[str, str]] = [
    # Secrets (masked by default)
    ("anthropic_key",      "sk-ant-api03-" + _pad(40)),
    ("openai_key",         "sk-" + _pad(40)),
    ("openai_project_key", "sk-proj-" + _pad(40)),
    ("aws_access_key",     "AKIA" + _pad(16, "FAKEDEMO0123ABCD")),
    ("google_api_key",     "AIza" + _pad(35)),
    ("google_oauth_token", "ya29." + _pad(40)),
    ("github_token",       "ghp_" + _pad(36)),
    ("github_oauth",       "gho_" + _pad(37)),
    ("github_pat",         "github_pat_" + _pad(82)),
    ("slack_token",        "xoxb-" + _pad(24)),
    ("slack_webhook",      "https://hooks.slack.com/services/T00/B00/" + _pad(24)),
    ("stripe_key",         "sk_test_" + _pad(28)),
    ("sendgrid_key",       "SG." + _pad(22) + "." + _pad(43)),
    ("npm_token",          "npm_" + _pad(36)),
    ("jwt",                "eyJ" + _pad(16) + ".eyJ" + _pad(16) + "." + _pad(20)),
    ("private_key_block",  "-----BEGIN RSA PRIVATE KEY-----"),
    ("generic_bearer",     "Bearer " + _pad(24)),
    ("db_uri_credentials", "postgresql://dbuser:" + _pad(12) + "@db.example.internal:5432"),
    # Financial / identity PII (masked by default)
    ("credit_card",        "4242 4242 4242 4242"),
    ("iban",               "DE89 3704 0044 0532 0130 00"),
    ("es_dni",             "12345678Z"),
    ("es_nie",             "X1234567L"),
    ("us_ssn",             "123-45-6789"),
    # Lower-sensitivity PII (detected, forwarded until you opt in)
    ("email",              "alice@example.com"),
    ("ipv4",               "192.0.2.45"),
    ("phone_intl",         "+1 415 555 0132"),
]


@dataclass
class Result:
    kind: str
    sample: str
    detected: bool       # the deterministic scanner recognized this kind
    action: str          # default policy action: pseudonymize | block | forward
    egress: str          # what leaves the machine: a placeholder, or the value itself
    masked: bool         # the value was replaced before egress
    leaked: bool         # the raw value is still present in the egress body
    roundtrip_ok: bool   # the vault restored the original bytes exactly


_POLICY = Policy.default()


def _check_one(kind: str, value: str) -> Result:
    detected = any(d.kind == kind for d in detectors.scan(value))
    action = _POLICY.action_for_kind(kind).value

    body = json.dumps(
        {"messages": [{"role": "user", "content": f"my {kind} is {value}"}]},
        ensure_ascii=False,
    ).encode()
    sanitized, vault, applied = sanitize_request_body(body, _POLICY)

    egress_text = sanitized.decode("utf-8", "replace")
    masked = kind in {k for k, _ in applied}
    leaked = value in egress_text

    # Simulate the cloud echoing the (masked) body back, then restore locally.
    restorer = StreamRestorer(vault)
    restored = restorer.feed(sanitized) + restorer.flush()
    roundtrip_ok = restored == body

    egress = vault.placeholder_for(value, kind) if masked else value
    return Result(kind, value, detected, action, egress, masked, leaked, roundtrip_ok)


def check() -> list[Result]:
    """Run the full matrix and return one Result per kind."""
    return [_check_one(kind, value) for kind, value in SAMPLES]


# --- presentation --------------------------------------------------------------
def _c(code: str, text: str, on: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if on else text


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _render(results: list[Result], on: bool) -> str:
    lines = [
        f"  {'KIND':<20} {'EXAMPLE (fake)':<26} {'DEFAULT':<8} {'WHAT THE CLOUD SEES':<28} STATUS",
        "  " + "─" * 96,
    ]
    for r in results:
        default = "forward" if r.action == "forward" else "mask"
        cells = f"  {r.kind:<20} {_trunc(r.sample, 26):<26} {default:<8} {_trunc(r.egress, 28):<28} "
        if r.action == "forward":
            status = _c("90", "· detected · opt-in to mask", on)
        elif (not r.leaked) and r.roundtrip_ok:
            status = _c("92", "✓ masked · restored", on)
        else:
            status = _c("91", "✗ FAILED", on)
        lines.append(cells + status)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    on = sys.stdout.isatty() and not os.getenv("NO_COLOR")
    results = check()
    masked = [r for r in results if r.action != "forward"]
    forwarded = [r for r in results if r.action == "forward"]

    print()
    print(_c("96;1", "  Exodus self-test — every detector kind on synthetic data", on))
    print(_c("90", f"  {len(results)} kinds · {len(masked)} masked by default · "
                   f"{len(forwarded)} detected/opt-in · every value is FAKE", on))
    print()
    print(_render(results, on))
    print()

    leaks = [r for r in masked if r.leaked]
    undetected = [r for r in results if not r.detected]
    rt_failed = [r for r in masked if not r.roundtrip_ok]
    ok = not leaks and not undetected and not rt_failed

    if ok:
        print(_c("92;1", f"  PASS  {len(masked)}/{len(masked)} protected values masked and "
                         "restored exactly · 0 leaked to egress", on))
    else:
        print(_c("91;1", f"  FAIL  leaks:{len(leaks)} undetected:{len(undetected)} "
                         f"roundtrip:{len(rt_failed)}", on))
    print()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
