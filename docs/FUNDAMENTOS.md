# Exodus — Theoretical & Practical Foundations

> **Purpose of this document.** This is the project's knowledge base: the theory, the practice, the threat model, the state of the art, and the evaluation plan. It is written so that the academic paper (`paper/exodus-paper.md`) can later be assembled from it. Keep it rigorous and honest — every claim here may end up in a peer-reviewed venue.

**Maintained by:** Proyecto Exodus
**Status:** working — M0–M4 milestones complete.

---

## 1. Problem statement & motivation

Modern LLM assistants are powerful precisely because they ingest rich context: source code, files, terminal output, personal notes. That same richness is a privacy liability:

1. **Exposure.** Everything sent to a cloud model is processed on third-party infrastructure.
2. **Retention & training.** Depending on the provider's terms, inputs may be retained or used to improve models. (Commercial/API terms frequently exclude training by default; consumer terms differ and change.)
3. **Profiling externalities.** The broader data economy turns behavioral exhaust into profiles. Reducing what you emit is a form of autonomy.

**Goal of Exodus:** minimize the sensitive data that reaches third-party servers **without destroying the utility** of the assistant, and **without overstating** the protection offered.

---

## 2. The fundamental impossibility (and what *is* possible)

### 2.1 You cannot hide a message from its own recipient

A common intuition is: "encrypt the chat so the provider's servers cannot decipher it, but the model still works." This is **impossible** under current cloud-inference architecture, for a structural reason:

> The model is a program **running on the provider's servers**. For it to understand text, plaintext (or a semantically equivalent representation) must exist in the context window **at inference time**, on that server. Encrypting the content from the server encrypts it from the model too.

Cryptography hides messages from a **third party on the channel** (an eavesdropper), **not from the recipient**. The provider is not the eavesdropper here — it is the recipient (the model is the party you are communicating *with*). You cannot establish a key "with the model" that the provider does not hold, because the provider's infrastructure runs the model's side of that key.

### 2.2 Utility and decodability are the same axis

There is no encoding that is simultaneously (a) structured enough for the cloud model to reason over it and (b) opaque to the server. The more "reasoned over" the input can be, the more recoverable its meaning is server-side — because the model's own understanding is a server-side computation (observable in activations and outputs). Strong encryption turns the input into high-entropy noise the model cannot use.

### 2.3 The one theoretical exception: FHE — and why it is out of scope

**Fully Homomorphic Encryption (FHE)** allows computation on ciphertext without decryption; in principle a model could run under FHE and the server would never see plaintext. In practice:

- It increases compute by **orders of magnitude** (thousands–millions×), violating any latency/cost constraint.
- It must be **implemented by the provider** in their inference engine; it cannot be bolted on from a client.
- No production frontier model offers it.

FHE is acknowledged here for completeness and **explicitly out of scope** for Exodus.

### 2.4 Corollary: the only real levers

If you cannot hide content from a model that must understand it, the levers that remain are:

1. **Do not send it** — keep computation local (full self-hosting).
2. **Send a sanitized surrogate** — pseudonymize values whose *meaning is irrelevant* to the task.
3. **Send a reduced form** — abstract/minimize content so less is exposed.
4. **Decide per fragment** which of the above to apply — *sensitivity-aware routing*.

Exodus is built on levers 2–4, with lever 1 available for the most sensitive fragments.

---

## 3. The solution spectrum

| Approach | Privacy | Utility | Hardware | Notes |
|---|---|---|---|---|
| **Cloud only** | None | Max | None | Status quo |
| **Pseudonymization proxy** | Hides flagged values | High | Light | Known technique; value-irrelevant data only |
| **Local abstraction** | Reduces identifiability | Medium–High | Light–Med | Lossy; abstracted facts still leave |
| **Sensitivity routing (Exodus)** | Graded, per-fragment | High (tunable) | Light–Med | Combines the above with a policy + local fallback |
| **Full self-hosting** | Maximal | Bounded by local model | Heavy | Data never leaves; weaker model |

---

## 4. Core concepts

### 4.1 Detection
- **Deterministic detectors:** regex + curated patterns for secrets (API keys, tokens, private keys), and structured PII (emails, IPs, file paths). High precision, fast, CPU-only.
- **Contextual detection:** a small local model (NER-style or a classification prompt) for entities that need context (personal names, proprietary identifiers).

### 4.2 Sensitivity classification
Each **span** (sentence, code block, entity) receives a sensitivity label. Inputs to the classifier:
- deterministic detector hits,
- contextual model output,
- **user policy** (keywords, file globs, project tags — e.g. "anything under `/secret/` is maximal").

**Design rule — fail closed:** when uncertain, treat a span as *more* sensitive, not less.

### 4.3 Policy tiers
| Tier | Action |
|---|---|
| `PUBLIC` | forward as-is |
| `LOW` | forward, pseudonymized |
| `MEDIUM` | forward, pseudonymized **+ abstracted** |
| `HIGH` | **local model only** |
| `SECRET` | block / require explicit user override |

Policy is user-owned and declarative (`policy.example.yaml`).

### 4.4 Reversible pseudonymization
Sensitive values are replaced by **stable, unique placeholder tokens**; the mapping (the *vault*) **never leaves the machine**. On the response path, placeholders are restored to real values locally. Critical for agentic clients: file edits round-trip correctly only if restoration is exact.

### 4.5 Local abstraction / minimization
A local model rewrites a sensitive span into a less-identifying but still useful form (e.g. an exact medical record → "adult with type-2 diabetes, no kidney issues"). **Lossy and honest:** the abstracted facts still leave the machine; this reduces, not eliminates, exposure.

### 4.6 Sensitivity-aware routing
The dispatcher sends each fragment to its policy-chosen backend (cloud vs local), then **merges** results. This is the project's center of gravity and its hardest engineering problem (see §6).

---

## 5. The agentic complication (why Claude Code is special)

The research literature targets *single-shot generic prompts*. Claude Code is **agentic**: it reads files, writes files, calls tools, and streams. This breaks naive routing:

1. **Streaming (SSE).** Responses arrive in chunks; restoration must happen on a token stream without splitting placeholder tokens across chunk boundaries.
2. **The edit loop.** The client applies returned edits to real files. Sanitize-on-send **must** be paired with exact restore-on-receive, or edits corrupt files.
3. **Local model ≠ agent.** A small local model is poor at driving tool-use loops. Therefore, *inside Claude Code*, the local model acts as a **pre/post-processor** (classify, abstract, pseudonymize) — **not** as the agent that answers tool-use turns. The "local model answers the whole turn" branch is reserved for a future standalone interface where we own the loop.

This agentic framing is Exodus's defensible niche: **applying sensitivity routing while preserving tool-use, file edits, and streaming.**

---

## 6. Open problems / research questions

1. **Classification precision under fail-closed bias** — minimizing leaks (false negatives) without crippling utility (false positives).
2. **Stream-safe restoration** — provably correct placeholder restoration over chunked SSE.
3. **Merge coherence** — stitching local + cloud outputs into a single coherent agentic response (the V2 frontier; cf. split/merge in Privacy Guard, PRISM).
4. **Abstraction fidelity vs. exposure** — quantifying the privacy/utility trade-off of local abstraction.

---

## 7. Threat model (summary)

See `docs/threat-model.md` for the full version.

- **Assets:** secrets, PII, proprietary code/logic, the local vault.
- **Adversary:** an honest-but-curious cloud provider + the broader retention/training/profiling pipeline; *not* a nation-state with local-host compromise.
- **Trust boundary:** the user's machine is trusted; everything past the proxy egress is untrusted.
- **Guarantee:** flagged sensitive spans (per policy) do not cross the boundary in plaintext.
- **Explicit non-guarantees:** misclassified spans; value-relevant tasks; anything the user overrides; metadata/timing.

---

## 8. Evaluation plan (metrics)

To make claims publishable, Exodus must be measured, not asserted:

- **Leak rate** — fraction of injected canary secrets/PII that reach the (mock) cloud endpoint. Target: → 0 at `SECRET`/`HIGH`.
- **Utility retention** — task success on a coding benchmark *with* vs *without* Exodus.
- **Latency overhead** — added per-request latency (classification + transform + restore).
- **Abstraction trade-off curve** — exposure vs. utility as a function of tier aggressiveness.

A reproducible harness lives under `tests/` and (later) `benchmarks/`.

---

## 9. Glossary

- **Span** — a unit of content classified independently (entity, sentence, code block).
- **Vault** — the local, never-exported map of placeholder ↔ real value.
- **Fail-closed** — on uncertainty, choose the more private action.
- **Surrogate** — the placeholder/abstracted value sent in place of the real one.

## 10. References

Bibliography (PRISM, PrivacyPAD, Privacy Guard, LLM-Guard, Presidio, FHE, etc.) is maintained in `paper/references.bib`.
