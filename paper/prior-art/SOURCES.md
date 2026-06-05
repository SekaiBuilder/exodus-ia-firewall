# Prior Art — the papers Exodus builds on

> **Honest positioning.** Exodus's contribution is an *engineering artifact* (an open,
> tested, Claude-Code-native implementation), **not** a new concept. The ideas below
> already exist in the literature; we cite them and stand on them.
>
> ⚠️ **PDFs are NOT committed** (third-party copyright) — they are git-ignored and kept
> locally only, for reading. Use the links to fetch them. Citations: `../references.bib`.
> Verify every citation (authors / venue / year) before any submission.

## Primary basis
### PRISM — Privacy-Aware Routing for Adaptive Cloud–Edge LLM Inference via Semantic Sketch Collaboration
- abs: https://arxiv.org/abs/2511.22788 · pdf: https://arxiv.org/pdf/2511.22788
- The closest to Exodus: profiles **entity-level sensitivity** on the edge and routes
  (cloud / edge / collaboration), with adaptive local differential privacy.
- **How Exodus differs:** we target the **agentic** loop (tool-use, file edits, SSE
  streaming) of a real tool (Claude Code), and ship a usable, tested artifact rather
  than a research prototype.

## Also foundational
- **PrivacyPAD** — RL for dynamic privacy-aware delegation. https://arxiv.org/abs/2510.16054
- **Privacy Guard & Token Parsimony** — on-prem SLM abstracts + decomposes prompts, re-routes high-risk sub-tasks. https://arxiv.org/abs/2603.28972
- **Privacy-Preserving LLMs Routing** — https://arxiv.org/abs/2604.15728
- **Collaborative Inference between Edge SLMs and Cloud LLMs (survey)** — https://arxiv.org/abs/2507.16731
- **EmojiPrompt** — generative prompt obfuscation for cloud LLMs. https://arxiv.org/abs/2402.05868
- **Hide-and-Seek (HaS)** — lightweight prompt privacy protection. https://arxiv.org/abs/2309.03057
- **The Fire Thief Is Also the Keeper** — balancing usability & privacy in prompts. https://arxiv.org/abs/2406.14318

## Reused engineering (tools, not papers)
- **Microsoft Presidio** — PII detection / anonymization (planned deeper integration). https://github.com/microsoft/presidio
- **LLM Guard** — anonymize / deanonymize scanners. https://github.com/protectai/llm-guard
