# Exodus inside a Trusted Execution Environment (Gramine / Intel SGX)

Exodus's vault holds your real secrets in memory while masked placeholders travel to the
cloud. On a normal host, anyone with root (or a malicious co-tenant on a shared machine)
can read that process memory. Running Exodus inside an **SGX enclave** closes that gap:
the CPU encrypts enclave memory with a key that never leaves the silicon, so **even the
machine's operator cannot read the vault**.

This document describes what is implemented, how to run it, and — in the spirit of
[the threat model](threat-model.md) — exactly what is and is not guaranteed.

---

## What is implemented

| Piece | Where | Status |
|---|---|---|
| Gramine manifest (LibOS wrapping, no code changes) | [`exodus.manifest.template`](../exodus.manifest.template) | working — `gramine-direct` |
| Attestation endpoint (`GET /_exodus/attest?nonce=…`) | `src/exodus/attest.py` | working — quote on SGX, labeled simulation elsewhere |
| Verifier client (`exodus verify`) | `src/exodus/verify.py` | working — nonce binding, quote parsing, MRENCLAVE pinning |
| Attested TLS channel (`exodus serve --tls`) | `src/exodus/tlsbind.py` | working — cert fingerprint folded into report_data (RA-TLS style) |

```
relying party                      enclave (Gramine LibOS)
─────────────                      ────────────────────────
exodus verify ── nonce ──────────► /_exodus/attest
              ◄── attestation doc ─   report_data = sha256(nonce)
verdict:                              + SGX quote (hardware only)
  ✓ nonce echoed (fresh, no replay)
  ✓ report_data commits to nonce
  ✓ quote binds the same commitment
  ✓ MRENCLAVE == pinned build        → TRUSTED
```

## Run it

```bash
# inside any x86_64 Linux with Gramine installed
gramine-manifest -Darch_libdir=/lib/x86_64-linux-gnu \
    exodus.manifest.template exodus.manifest
gramine-direct exodus          # simulation (no SGX hardware needed)
# gramine-sgx exodus           # same manifest, real enclave, on SGX hardware

# from anywhere that can reach the proxy
exodus verify --allow-simulated            # development
exodus verify --mrenclave <expected-hex>   # production: pin the build

# attested TLS: the channel itself is bound to the enclave
exodus serve --tls                         # self-signed cert, fingerprint in report_data
exodus verify --url https://host:8787 ...  # captures the cert, requires it in the quote
```

With `--tls`, certificate validation is *replaced* by attestation binding: a
man-in-the-middle would present a different certificate, whose fingerprint the
enclave would never sign into its report_data. This is the RA-TLS pattern —
trust comes from the silicon, not from a certificate authority.

`exodus verify` exits `0` only when the document passes every check; simulated
documents are rejected unless `--allow-simulated` is given, so the strict mode is
safe to use in scripts and CI.

## Honest scope

- **`gramine-direct` is functional simulation.** It proves the application runs
  unmodified under the LibOS and lets verifier code be developed, but provides **no
  hardware protection** — the attestation document says `"simulated": true` and the
  verifier treats it as untrusted by default. Hardware guarantees require SGX-capable
  CPUs (e.g. Azure DCsv3, on-prem Xeon with SGX enabled) and `gramine-sgx`.
- **The verifier checks structure and binding, not Intel's signature chain.** Full DCAP
  verification (quote signature → PCK certificate → Intel root CA) needs Intel's QVL or
  a PCCS deployment; the verifier surfaces MRENCLAVE/MRSIGNER so that step can be added
  on top without changing the protocol.
- **Attestation proves *which code* runs *where* — nothing more.** A trusted enclave
  running a build you haven't audited is still a leap of faith; pin MRENCLAVE to a build
  you can reproduce.

## Why this matters for agentic AI

Agent-to-agent protocols (MCP and friends) increasingly route secrets through
intermediaries. An Exodus instance that can *prove* it runs inside an enclave can be
trusted as a privacy gateway by parties who do not trust the machine it runs on —
the verifier in this repo is the client half of that handshake.
