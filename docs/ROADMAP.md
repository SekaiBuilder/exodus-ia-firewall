# Exodus — Roadmap

> Ship a real, honest artifact early; layer the research-grade differentiators on top.
> A milestone is **done** only when its invariants and tests pass.

## M0 — Foundations ✅ (in progress)
- [x] Repository scaffold, theory, structure, architecture diagrams
- [x] Threat model and paper base
- [x] `pyproject.toml` resolves; `pip install -e .` works
- [ ] CI: lint (ruff) + `pytest` green

## M1 — Transparent proxy (no privacy logic yet) ✅ DONE (unit + live e2e)
**Goal:** Claude Code works *through* Exodus with zero behavior change.
- [x] `proxy/server.py`: catch-all reverse proxy, pass-through
- [x] SSE streaming pass-through, faithful (unit-tested)
- [x] `anthropic_client.py`: upstream streaming forwarder
- [x] **Invariant:** identical Claude Code experience via `ANTHROPIC_BASE_URL` — real Claude Code request relayed (200 OK), 2026-06-03

## M2 — Secret firewall (the first real value) ✅ DONE (unit-verified)
**Goal:** secrets/credentials never leave; restored on the way back.
- [x] `detectors.py`: regex for keys/tokens/secrets (Presidio NER → M4)
- [x] `pseudonymize.py`: reversible substitution + in-memory vault
- [x] Stream-safe restoration (sentinel tokens + incremental UTF-8 decode)
- [x] **Invariants:** INV-1, INV-2, INV-3 — covered by `tests/test_firewall.py`

## M3 — Policy engine + audit ✅ DONE (unit-verified)
- [x] `policy.py` + `policy.example.yaml`: kind → tier → action, user-configurable (path globs → later)
- [x] `audit/log.py`: transparent JSONL trail (kind + action + ts, never values)
- [x] `exodus serve` + `exodus audit` (summary by kind/action + recent rows)

## M4 — Sensitivity classifier + local model ✅ DONE (unit-verified + live)
- [x] `local_model/runtime.py`: real Ollama client (MLX later)
- [x] `sensitivity.py`: contextual classification via local model (PUBLIC/LOW/MEDIUM/HIGH, fail-closed parse)
- [x] `abstract.py`: local abstraction (improved prompt + example; best-effort, lossy)
- [x] **Invariant:** INV-4 — fail-closed BLOCK on local-model failure (tested)
- [x] proxy wiring: opt-in `EXODUS_LOCAL_MODEL`, contextual pass runs BEFORE the firewall
- [~] abstraction quality: much improved (removes name/age/ID/street); coarse city may remain + may translate language — best-effort, see threat-model §5

## M5 — Evaluation & paper
- [ ] Benchmark harness: leak rate, utility retention, latency overhead
- [ ] Fill `paper/exodus-paper.md` §3–§6 with results
- [ ] Reproducibility: scripts + fixtures

## V2 — Standalone interface (research frontier)
- [ ] Own the loop → local model *answers* the most sensitive turns
- [ ] Span-level **split + merge** (cf. PRISM, Privacy Guard)
- [ ] Spanish edition of docs (`README.es.md`, etc.)

## V3 — Generalization
- [ ] Other clients (OpenAI-compatible) beyond Claude Code
- [ ] Pluggable detectors/classifiers; policy marketplace
