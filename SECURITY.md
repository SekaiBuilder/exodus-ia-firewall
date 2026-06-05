# Security Policy & Assessment

Exodus is a security-sensitive tool: a local proxy that handles your secrets and PII. This
document states its security model, its **testable guarantees**, its attack surface, and —
just as importantly — what it does **not** protect. Limits are documented honestly rather
than implying a guarantee we cannot keep.

## 1. Security model in one line

> Exodus minimizes the sensitive data that leaves your machine. It is **harm reduction, not
> invisibility** — the cloud model runs on the provider's servers, so your prompt must reach
> them; Exodus removes the sensitive *parts* before they do.

## 2. Trust boundary & data flow

```
  YOUR MACHINE (trusted)                          │  PROVIDER (untrusted for privacy)
  ──────────────────────────────────────────────  │  ─────────────────────────────────
  Agent (Claude Code / Codex)                      │
        │  HTTP, localhost only                     │
        ▼                                           │
  Exodus proxy ── detect ─ policy ─ mask ─────────►│  api.anthropic.com / api.openai.com
        │  real values kept in an in-memory vault   │  (sees only placeholders for masked data)
        ◄── restore placeholders in the response ───│
```

- Exodus binds to `127.0.0.1` by default — **not** exposed to the network.
- The **vault** (real value ↔ placeholder map) lives in memory and is **never serialized**
  upstream or to disk.
- The only component allowed to cross the trust boundary is the upstream forwarder.

## 3. Core invariants (the guarantees we test)

Enforced in code and covered by the test suite (`tests/test_firewall.py`):

| Invariant | Guarantee |
|---|---|
| **INV-1** | No real value of a detected **secret** crosses egress — a placeholder goes instead. |
| **INV-2** | The vault is never sent upstream nor written to the audit log. |
| **INV-3** | A pseudonymized value restored on the response path round-trips **exactly** (your files/code are never corrupted). |
| **INV-4** | **Fail-closed:** if the local model is engaged and fails mid-request, the content is **blocked**, never forwarded raw. |

The audit log records *kinds and actions only* — **never values**.

## 4. What Exodus protects

- **Secrets with a known signature** — Anthropic / OpenAI / AWS / Google / GitHub / Slack /
  Stripe / SendGrid / npm keys, JWTs, PEM private keys, Bearer tokens, and DB URIs with
  embedded credentials.
- **Structured PII that validates** — credit cards (Luhn), IBAN (mod-97), Spanish DNI/NIE,
  US SSN. Validators keep false positives near zero.
- **Free-text sensitivity** (optional on-device model) — names, addresses, sensitive prose,
  in any language.

## 5. What Exodus does NOT protect — honest non-guarantees

- **Unrecognized secrets.** A value with no signature and no validatable structure (a weak
  password like `1234567`, a bespoke internal token) looks like normal text and is **not**
  masked unless the optional local model catches it.
- **Your identity / metadata.** The provider still receives your authenticated account and
  request metadata. Exodus protects *content*, not *who you are*.
- **The general meaning of what you ask.** Abstraction is **lossy**: identifiers are removed,
  but the gist (e.g. "a patient has asthma") still leaves the machine.
- **GUI consumer apps.** Claude Desktop / ChatGPT app do not honor a base-URL override;
  intercepting them would require TLS interception (out of scope). Exodus covers CLIs/SDKs.
- **A compromised local machine.** Exodus assumes your own machine is trusted. Local malware
  can read plaintext before Exodus ever sees it.

## 6. Attack surface

- **Local listener** (`127.0.0.1:8787`) — reachable only by local processes. Do **not** bind
  it to a public interface.
- **Upstream TLS** — forwarded over HTTPS via `httpx` with certificate verification enabled.
- **Optional inspection log** (`EXODUS_INSPECT`) — writes **full plaintext, including secrets**,
  for debugging *your own* traffic. **Off by default and git-ignored.** Treat any such file as
  sensitive and delete it when done.
- **Local model weights** — downloaded once from Hugging Face; pin and verify the source if
  your threat model requires supply-chain assurance.

## 7. Secure defaults

- Binds to localhost; vault in memory; audit stores no values.
- **Fail-closed policy** — an unknown detector kind is treated as a secret (masked); an
  unknown tier maps to `block`.
- The local-model layer is **opt-in**; the deterministic firewall needs no model.

## 8. Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, open a private
**GitHub Security Advisory** on this repository (Security → *Report a vulnerability*). We aim
to acknowledge promptly and ask for reasonable time to fix before public disclosure.

## 9. Scope of this assessment

This describes the privacy/security properties of the proxy and its detectors. It is **not**
a third-party audit and does not certify regulatory compliance (GDPR, HIPAA, etc.). For
high-stakes use, commission an independent review.
