# Exodus — Threat Model

> Honesty is the product. This document states **exactly** what Exodus defends against and what it does not. If a claim cannot be defended here, it must not appear in the README.

## 1. Assets (what we protect)

| Asset | Examples |
|---|---|
| Secrets | API keys, OAuth tokens, private keys, `.env` values, passwords |
| PII | Names, emails, phone numbers, IP addresses, physical/postal addresses |
| Proprietary content | Trade-secret algorithms, unreleased business logic, internal hostnames |
| The vault | The local placeholder ↔ real-value mapping |

## 2. Adversary model

**In scope — honest-but-curious cloud + data economy:**
- A cloud LLM provider that receives, may log, may retain, and may (per terms) train on inputs.
- Downstream retention/profiling pipelines fed by emitted data.

**Out of scope (explicitly):**
- An attacker with **local code execution** on the user's machine (they can read the vault and plaintext directly — game over, by construction).
- A **malicious provider** that actively backdoors inference (FHE territory; see `FUNDAMENTOS.md` §2.3).
- **Network metadata / timing** side channels (Exodus hides *content*, not the fact that you made a request, when, or how large).
- **Re-identification** of abstracted content by a determined analyst.

## 3. Trust boundary

```
[ user's machine — TRUSTED ]  ── egress ──►  [ Anthropic API — UNTRUSTED ]
   Claude Code, Exodus, Ollama, vault              cloud inference
```

Everything before egress is trusted. The guarantee concerns **what crosses egress**.

## 4. Security guarantee (what Exodus promises)

> For any span classified at `SECRET` or `HIGH` under the active policy, the **real plaintext value does not cross the egress boundary**. `SECRET` spans are blocked or pseudonymized; `HIGH` spans are handled by the local model or abstracted before egress. The vault is never serialized to the wire.

## 5. Non-guarantees (what Exodus does NOT promise)

1. **Classifier completeness.** A sensitive span that the classifier misses (`false negative`) **will** be sent. Mitigation: fail-closed bias, deterministic detectors for high-value secrets, user policy overrides, audit review.
2. **Value-relevant tasks.** If the task genuinely needs the real value (e.g. "is this API key valid?"), Exodus cannot both hide it and help.
3. **User overrides.** If the user confirms sending a `SECRET`/`HIGH` span, that is their decision and it leaves.
4. **Abstraction leakage.** Abstracted/minimized content is *reduced*, not *removed* — the residual still leaves.
5. **Metadata.** Request existence, timing, and size are visible to the provider.

## 6. Failure modes & mitigations

| Failure | Impact | Mitigation |
|---|---|---|
| Placeholder split across SSE chunks | Corrupted restore | Sentinel tokens + minimal buffering |
| Vault leaked to disk/log | PII exposure | Vault in memory by default; git-ignore; never logged |
| Classifier false negative | Leak | Fail-closed; deterministic high-value detectors; canary tests |
| Restore mismatch in edit loop | File corruption | Unique stable placeholders; round-trip tests |
| Local model unavailable | `HIGH` span cannot be handled | Block + warn (never silently forward) |

## 7. Testable invariants

- **INV-1:** No `SECRET` real value appears in any payload sent upstream (canary test).
- **INV-2:** The vault is never present in any outbound request or any log line.
- **INV-3:** A round-tripped file edit reproduces the original real values byte-for-byte.
- **INV-4:** On local-model failure, `HIGH`/`SECRET` spans are blocked, never forwarded.

These invariants are the acceptance criteria for the MVP and the basis of the evaluation harness.
