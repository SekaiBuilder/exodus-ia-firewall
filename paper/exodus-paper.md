# Exodus: Sensitivity-Aware Privacy Routing for Agentic Coding Assistants

**Authors:** Francesco Catania (@sekaibuilder)
**Status:** Draft — abstract & introduction written; §3–§7 to be filled from implementation and evaluation.
**Companion artifacts:** source (`/src`), foundations (`docs/FUNDAMENTOS.md`), threat model (`docs/threat-model.md`).

---

## Abstract

Cloud large language models (LLMs) deliver state-of-the-art assistance precisely because they ingest rich user context — including source code, files, and personal data — onto third-party infrastructure. This creates an inherent tension: the same context that powers the assistant is exposed to retention, training, and downstream profiling. We observe that the strong form of the user's wish — *encrypt the data so the provider cannot read it while the model still uses it* — is impossible under cloud inference, because the model executes on the provider's servers and thus requires plaintext at inference time; cryptography cannot hide a message from its own recipient. We therefore reframe the problem as **data minimization via sensitivity-aware routing**: classifying content fragment-by-fragment and deciding, per fragment, whether to forward it to the cloud (optionally pseudonymized or abstracted) or to retain it on a local model. While such cloud–edge privacy routing is an active research area, prior work targets generic single-shot prompts. **Exodus** applies sensitivity routing to the **agentic coding loop** — preserving tool use, file edits, and token streaming — by interposing a local, Anthropic-API-compatible proxy in front of Claude Code. We contribute (i) a layered, open-source implementation, (ii) an explicit, testable threat model with fail-closed invariants, and (iii) a reproducible evaluation of leak rate, utility retention, and latency overhead. Exodus is positioned as a usable engineering artifact bridging privacy research and a widely used agentic tool, with honestly documented limits rather than false guarantees.

---

## 1. Introduction

### 1.1 Motivation
Agentic coding assistants such as Claude Code have moved LLMs from chat boxes into the developer's working directory: they read files, run tools, and edit code autonomously. Their usefulness scales with the context they are given, which routinely includes secrets, personally identifiable information (PII), and proprietary logic. Once transmitted, this context leaves the user's control and enters a pipeline whose retention and training behavior is governed by terms the user rarely audits and cannot enforce technically.

### 1.2 The impossibility we must respect
A natural request is an "obfuscator" that renders chat content undecipherable to the provider while keeping the model fully functional. We argue this is structurally impossible (Section 2; expanded in `FUNDAMENTOS.md` §2): the model is a process on the provider's servers, so it needs plaintext at inference; and the provider is the *recipient*, not a *middleman*, so end-to-end encryption does not apply. The only theoretical escape, fully homomorphic encryption, is many orders of magnitude too expensive and must be implemented provider-side. **Utility and decodability lie on the same axis.**

### 1.3 Reframing: minimize, don't obfuscate
If content destined for a model that must understand it cannot be hidden, the actionable levers are: (1) do not send it (local compute); (2) send a pseudonymized surrogate when the *value* is irrelevant to the task; (3) send an abstracted, reduced form; and (4) decide *per fragment* which lever applies. Levers (2)–(4) define **sensitivity-aware routing**.

### 1.4 Why the agentic setting is different
Existing privacy-routing systems assume a single prompt and a single response. Claude Code violates both assumptions: responses **stream** (restoration must be stream-safe), the client **applies edits to real files** (sanitize/restore must round-trip exactly), and a small local model **cannot drive** the tool-use loop (so locally it must act as a pre/post-processor, not as the agent). Handling sensitivity routing *without breaking agentic behavior* is, to our knowledge, unaddressed.

### 1.5 Contributions
1. A **layered, open-source proxy** that interposes a privacy pipeline (detect → classify → policy → transform → route → audit) between Claude Code and the Anthropic API.
2. An **explicit threat model** with fail-closed, testable invariants (no `SECRET` value crosses egress; vault never serialized; edits round-trip; fail-closed on local outage).
3. A **reproducible evaluation** methodology for leak rate, utility retention, and latency overhead.
4. An **honesty-first framing**: documented non-guarantees that prevent false security.

---

## 2. Background & Related Work

*(See `references.bib`.)*

- **Cloud–edge privacy routing.** PRISM routes by entity-level sensitivity with adaptive local differential privacy and an edge-refined "semantic sketch." PrivacyPAD learns delegation via reinforcement learning. Privacy Guard & Token Parsimony decomposes prompts and re-routes high-risk sub-tasks. Exodus differs by targeting the *agentic* loop and shipping a usable artifact rather than a research prototype.
- **Prompt anonymization.** Presidio, LLM-Guard, anonLLM, and CleanPrompt provide PII detection and reversible (de)anonymization. Exodus reuses this layer (lever 2) rather than reinventing it.
- **Obfuscation & split inference.** EmojiPrompt and Hide-and-Seek obfuscate prompts; split-inference partitions models so embeddings stay local. We position these against the utility/decodability trade-off discussed in §1.2.

> **Honest positioning.** Exodus's novelty is *application and engineering* (agentic, open, benchmarked, honestly bounded), **not** a new routing concept.

## 3. System Design
_[TODO: layered architecture; expand from `docs/ARQUITECTURA.md`.]_

## 4. Implementation
_[TODO: proxy/SSE, detectors, policy, vault, Ollama runtime; pin versions.]_

## 5. Evaluation
_[TODO: leak rate, utility retention, latency overhead, abstraction trade-off curve; report on canary corpus + coding benchmark.]_

## 6. Limitations & Ethics
_[TODO: false negatives, metadata side channels, abstraction residue; the duty not to provide false security.]_

## 7. Conclusion
_[TODO]_

## References
See `references.bib`.
