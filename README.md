# Exodus 🛡️

> A local, **sensitivity-aware privacy router** for agentic LLM clients — Claude Code and Codex.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-46%20passing-brightgreen)
![Status](https://img.shields.io/badge/status-M0--M4%20working-success)

**🌐 English (primary)** · [Español](esp/README.md)

Exodus runs on your own machine, between your AI coding agent and the cloud API, and
**minimizes the sensitive data that leaves it** — masking secrets and PII *before* they
are sent, and restoring them transparently in the response so your tools keep working.

---

## ⚠️ Honest scope (read this first)

Exodus is **harm reduction, not invisibility.** It does not sell an impossible promise.

- The model runs **on the provider's servers**, so your prompt *must* reach them for the
  AI to answer. Exodus does not make your message invisible — it **removes the sensitive
  parts before they travel**.
- It masks what it can **recognize**: secrets with a known signature (`sk-ant-…`, `AKIA…`,
  JWTs…) and structured PII that **validates** (credit cards via Luhn, IBAN via mod-97,
  DNI/NIE, SSN). A random string with no signature is *not* detectable as a secret.
- It does **not** hide your identity/metadata — the provider still knows it's your account.
- The optional local-model layer (M4) is **lossy**: it strips identifiers from free text,
  but the general meaning still leaves the machine.
- **GUI consumer apps (Claude Desktop, ChatGPT app) are out of scope** — Exodus protects
  the *agentic / API loop* (CLIs, SDKs), the high-risk surface where an agent autonomously
  ships your code and secrets to the cloud.

Full, formal threat model: [`docs/threat-model.md`](docs/threat-model.md). **Read it before
trusting Exodus with anything.**

---

## How it works

```
Claude Code / Codex ──► 🛡 Exodus (localhost) ──► api.anthropic.com / api.openai.com
   set *_BASE_URL          │  detect → policy → mask (reversible) → forward
                           └─ real values stay in a local in-memory vault;
   restored response  ◄────── placeholders restored on the way back
```

Your client honors a base-URL env var (`ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`). Point it at
Exodus. Exodus scans each request, replaces detected secrets/PII with reversible placeholders
(`⟪EXODUS:kind:N⟫`), forwards the cleaned request, and restores the originals in the response.
Diagrams: [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

---

## Install

Requires Python ≥ 3.11.

```bash
git clone <repo-url> exodus && cd exodus
python -m venv .venv && source .venv/bin/activate
pip install -e .                 # core firewall — zero model, zero Ollama
pip install -e ".[local]"        # optional: embedded local model (M4 free-text layer)
```

---

## How to use

### 1 · Start Exodus
```bash
exodus serve                     # listens on http://127.0.0.1:8787
```

### 2a · Claude Code (Anthropic)
In the terminal where you launch Claude Code — **export first, then launch**:
```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
claude
```
The `WITH EXODUS` status indicator means you're protected.

### 2b · Codex (OpenAI)
Run a second Exodus pointed at OpenAI, on another port:
```bash
EXODUS_UPSTREAM=https://api.openai.com EXODUS_PORT=8788 exodus serve
```
Add a provider in `~/.codex/config.toml`:
```toml
[model_providers.exodus]
name     = "exodus"
base_url = "http://127.0.0.1:8788/v1"
env_key  = "OPENAI_API_KEY"

model_provider = "exodus"
```
(Works when Codex authenticates with an OpenAI API key.)

### 3 · See what actually left your machine
```bash
exodus audit                     # kinds + actions that were masked — never the values
```
Opt-in debug (full plaintext of **your own** traffic; off by default, git-ignored):
```bash
EXODUS_INSPECT=on exodus serve
```

---

## What it detects

**Secrets** — always masked:
Anthropic · OpenAI (+ `sk-proj-`) · AWS · Google (API + OAuth) · GitHub (token / PAT / OAuth)
· Slack (token + webhook) · Stripe · SendGrid · npm · JWT · PEM private keys · generic Bearer
· DB connection URIs with credentials.

**Structured PII** — validated, masked by default:
credit cards (Luhn) · IBAN (mod-97) · Spanish DNI / NIE · US SSN.

**Lower-sensitivity PII** — detected, opt-in:
email · IPv4 · international phone.

**Free text** (names, addresses, sensitive prose — any language) → the optional local model
below. Regex can't scale to every country and language; the model is the multilingual answer.

You own the policy: edit [`src/exodus/policy/policy.example.yaml`](src/exodus/policy/policy.example.yaml)
to set each kind's action (`forward` / `pseudonymize` / `block`). **Fail-closed** by default —
an unknown kind is treated as a secret.

---

## Optional local model (M4)

For sensitive content with *no signature*, Exodus runs a small model **embedded in-process**
(llama.cpp + a GGUF — **no Ollama daemon**) to classify and abstract it. Off by default; the
core firewall works without it.

```bash
pip install -e ".[local]"
EXODUS_LOCAL_MODEL=on exodus serve   # downloads a small multilingual model once, then offline
```
Backend is pluggable: `EXODUS_LOCAL_BACKEND=embedded` (default) or `ollama`.

Example — the model strips identifiers, keeps the gist:
```
in:  Patient John Smith, 47, record #55231, 12 Oak St, Madrid, has asthma.
out: Patient has asthma.
```

---

## Configuration

Copy `.env.example` → `.env`. Key variables:

| Variable | Purpose |
|---|---|
| `EXODUS_UPSTREAM` | provider API to forward to (Anthropic default; `https://api.openai.com` for Codex) |
| `EXODUS_HOST` / `EXODUS_PORT` | where Exodus listens (default `127.0.0.1:8787`) |
| `EXODUS_POLICY_FILE` | your policy YAML |
| `EXODUS_LOCAL_MODEL` / `EXODUS_LOCAL_BACKEND` | enable + choose the M4 backend |
| `EXODUS_INSPECT` | debug log of your own traffic (full plaintext; off by default) |

---

## Tests
```bash
pip install -e ".[dev]" && pytest        # 46 passing
```

---

## Where Exodus fits (honest positioning)

Sensitivity-aware cloud/edge routing is an active research area (PRISM, PrivacyPAD,
Privacy Guard — see [`paper/references.bib`](paper/references.bib)), mostly on *generic*
prompts. **Exodus's contribution is an engineering artifact:** an open-source implementation
that brings these ideas to the **agentic coding loop** (tool-use, file edits, SSE streaming),
with a reversible vault, an honest threat model, and a self-contained local model. See
[`paper/`](paper/).

## Project layout & roadmap
Structure: [`docs/ESTRUCTURA.md`](docs/ESTRUCTURA.md) · Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)
· Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## License
MIT © Francesco Catania ([@sekaibuilder](https://github.com/sekaibuilder)). See [`LICENSE`](LICENSE).

## Disclaimer
Exodus is a **harm-reduction** tool, not a guarantee of anonymity. It reduces the sensitive
data that reaches third-party servers; it does not make you invisible. Do not feed it secrets
you cannot afford to leak on the assumption that it is infallible.
