# Exodus — Project Structure (annotated & enumerated)

> The "textual UML": every file in the repository, numbered, with its single responsibility.
> Principle: **one module, one job.** A reviewer should predict a file's contents from its path.

## 0. Repository tree

```
proyecto-exodus/
├── README.md                      # (1)  Public entry point
├── LICENSE                        # (2)  MIT
├── .gitignore                     # (3)  Ignore secrets, vault, caches
├── pyproject.toml                 # (4)  Packaging + dependencies + tooling
├── .env.example                   # (5)  Configuration template
├── CONTRIBUTING.md                # (6)  How to contribute
├── SECURITY.md                    # (7)  Security policy & assessment
│
├── docs/
│   ├── FUNDAMENTOS.md             # (8)  Theory & knowledge base (feeds the paper)
│   ├── ESTRUCTURA.md              # (9)  This file
│   ├── ARQUITECTURA.md            # (10) Graphical diagrams (Mermaid)
│   ├── threat-model.md            # (11) Formal threat model
│   └── ROADMAP.md                 # (12) Milestones MVP → V2 → V3
│
├── paper/
│   ├── exodus-paper.md            # (13) Academic paper (abstract + intro written)
│   └── references.bib             # (14) Bibliography / prior art
│
├── src/exodus/
│   ├── __init__.py                # (15) Package marker + version
│   ├── proxy/
│   │   ├── server.py              # (16) FastAPI app: /v1/messages + SSE streaming
│   │   └── anthropic_client.py    # (17) Upstream forwarder to api.anthropic.com
│   ├── classify/
│   │   ├── detectors.py           # (18) Regex + Presidio deterministic detectors
│   │   └── sensitivity.py         # (19) Span sensitivity classifier (local model)
│   ├── policy/
│   │   ├── policy.py              # (20) Tier engine PUBLIC..SECRET
│   │   └── policy.example.yaml    # (21) Declarative user policy template
│   ├── transform/
│   │   ├── pseudonymize.py        # (22) Reversible substitution + local vault
│   │   └── abstract.py            # (23) Local-model abstraction / minimization
│   ├── local_model/
│   │   └── runtime.py             # (24) Ollama (now) / MLX (later) client
│   └── audit/
│       └── log.py                 # (25) Transparent audit trail
│
└── tests/
    └── test_smoke.py              # (26) Smoke tests + leak-canary scaffold
```

## 1. Layered responsibilities

The code is organized as a **pipeline of single-purpose layers**. Data flows down on the request, up on the response.

| # | Layer | Package | Owns | Must NOT |
|---|---|---|---|---|
| L0 | **Transport** | `proxy/` | Speak the Anthropic Messages API; stream SSE; forward upstream | Make privacy decisions |
| L1 | **Detection** | `classify/detectors.py` | Find secrets/PII deterministically | Decide routing |
| L2 | **Classification** | `classify/sensitivity.py` | Assign a sensitivity label per span | Mutate content |
| L3 | **Policy** | `policy/` | Map sensitivity → action (the tiers) | Detect or transform |
| L4 | **Transform** | `transform/` | Pseudonymize / abstract; own the vault | Route or call upstream |
| L5 | **Local compute** | `local_model/` | Run the local model (classify/abstract) | Know about HTTP/proxy |
| L6 | **Audit** | `audit/` | Record what left and what was masked | Alter the decision |

**Dependency rule:** higher layers may import lower-utility helpers, but `classify/`, `policy/`, `transform/`, `local_model/`, and `audit/` must remain **independently testable** and free of `proxy/` imports. This keeps the privacy core reusable by the future standalone interface.

## 2. Data contracts (to be formalized in code)

- `Span` — `{text, start, end, kind, sensitivity, source}`
- `PolicyDecision` — `{span, tier, action}` where action ∈ `{FORWARD, PSEUDONYMIZE, ABSTRACT, LOCAL, BLOCK}`
- `VaultEntry` — `{placeholder, real_value, scope}` (local only; never serialized to the wire)
- `AuditRecord` — `{ts, request_id, span_kind, action, backend}`

## 3. Naming & conventions

- Python ≥ 3.11, type hints everywhere, `ruff` for lint/format.
- No secret ever logged in plaintext (audit logs store *kinds*, not values).
- Files that may contain real values (`*.vault`, `.env`) are git-ignored.
