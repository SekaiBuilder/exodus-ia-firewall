# Exodus — Architecture (graphical)

> Diagrams use [Mermaid](https://mermaid.js.org/), which renders natively on GitHub.
> Keep these in sync with the code; update them on any architectural change.

---

## 1. Component diagram

```mermaid
flowchart TD
    CC["Claude Code<br/>(ANTHROPIC_BASE_URL → localhost)"]

    subgraph EXODUS["Exodus — local privacy router"]
        direction TB
        PRX["proxy/server.py<br/>L0 · Messages API + SSE"]
        DET["classify/detectors.py<br/>L1 · regex + Presidio"]
        SEN["classify/sensitivity.py<br/>L2 · sensitivity per span"]
        POL["policy/policy.py<br/>L3 · tier engine"]
        TRA["transform/*<br/>L4 · pseudonymize / abstract"]
        VLT[("local vault<br/>placeholder ↔ real")]
        LM["local_model/runtime.py<br/>L5 · Ollama"]
        AUD["audit/log.py<br/>L6 · audit trail"]
        FWD["proxy/anthropic_client.py<br/>upstream forwarder"]
    end

    API["api.anthropic.com<br/>(cloud — untrusted)"]

    CC -->|request| PRX
    PRX --> DET --> SEN --> POL --> TRA
    TRA <--> VLT
    TRA -->|MEDIUM/HIGH| LM
    POL --> AUD
    TRA -->|sanitized| FWD
    FWD -->|only what is allowed| API
    API -->|response| FWD
    FWD -->|restore via VLT| PRX
    PRX -->|stream| CC

    classDef trusted fill:#e6ffe6,stroke:#2e7d32;
    classDef untrusted fill:#ffe6e6,stroke:#c62828;
    class EXODUS,CC trusted;
    class API untrusted;
```

**Trust boundary:** everything inside the green box runs on the user's machine. The red node is the only thing on the far side of the boundary — and it only ever receives what policy allowed.

---

## 2. Request sequence (happy path)

```mermaid
sequenceDiagram
    participant CC as Claude Code
    participant PX as Exodus Proxy
    participant CL as Classifier
    participant PO as Policy
    participant TR as Transform (+Vault)
    participant LM as Local Model
    participant AN as Anthropic API

    CC->>PX: POST /v1/messages (code, files, prompt)
    PX->>CL: segment + detect spans
    CL->>PO: spans + sensitivity labels
    PO->>TR: per-span decisions
    alt SECRET / HIGH
        TR->>LM: abstract or handle locally
        LM-->>TR: surrogate / local result
    end
    TR->>TR: pseudonymize (store map in Vault)
    TR->>AN: forward sanitized request
    AN-->>PX: streamed response (SSE)
    PX->>TR: restore placeholders (from Vault)
    PX-->>CC: streamed, restored response
    PX->>PX: write AuditRecord
```

---

## 3. Routing decision (per span)

```mermaid
flowchart TD
    S["Span"] --> D{"Deterministic hit?<br/>(key/token/PII)"}
    D -->|yes: secret| SEC["SECRET → block / pseudonymize"]
    D -->|yes: PII| LOW["LOW → pseudonymize + forward"]
    D -->|no| C{"Contextual sensitivity?"}
    C -->|high| H["HIGH → local model only"]
    C -->|medium| M["MEDIUM → abstract + forward"]
    C -->|low/unknown| U{"Policy override?<br/>(globs, tags)"}
    U -->|matches sensitive| H
    U -->|none| PUB["PUBLIC → forward as-is"]

    classDef stop fill:#ffd6d6,stroke:#c62828;
    classDef warn fill:#fff3cd,stroke:#f9a825;
    classDef ok fill:#d6ffd6,stroke:#2e7d32;
    class SEC,H stop;
    class LOW,M warn;
    class PUB ok;
```

> **Fail-closed:** the `unknown` path biases toward the policy/override check rather than defaulting to `PUBLIC`.

---

## 4. Deployment view (MVP, on the user's Mac)

```mermaid
flowchart LR
    subgraph MAC["MacBook Air M5 · 32 GB (trusted)"]
        CC2["Claude Code CLI"]
        EX["Exodus proxy<br/>:8787"]
        OL["Ollama<br/>:11434 (local model)"]
    end
    NET(["Internet"])
    AN2["Anthropic API"]

    CC2 --> EX
    EX --> OL
    EX --> NET --> AN2
```
