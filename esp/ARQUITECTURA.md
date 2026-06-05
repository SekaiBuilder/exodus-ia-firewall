# Exodus — Arquitectura (gráfica)

> **Edición en español** (la versión canónica es [`docs/ARQUITECTURA.md`](../docs/ARQUITECTURA.md)). Los diagramas usan [Mermaid](https://mermaid.js.org/), que se renderiza nativamente en GitHub. Mantenerlos en sync con el código.

---

## 1. Diagrama de componentes

```mermaid
flowchart TD
    CC["Claude Code<br/>(ANTHROPIC_BASE_URL → localhost)"]

    subgraph EXODUS["Exodus — router de privacidad local"]
        direction TB
        PRX["proxy/server.py<br/>L0 · API Mensajes + SSE"]
        DET["classify/detectors.py<br/>L1 · regex + Presidio"]
        SEN["classify/sensitivity.py<br/>L2 · sensibilidad por fragmento"]
        POL["policy/policy.py<br/>L3 · motor de niveles"]
        TRA["transform/*<br/>L4 · seudonimizar / abstraer"]
        VLT[("bóveda local<br/>marcador ↔ real")]
        LM["local_model/runtime.py<br/>L5 · Ollama"]
        AUD["audit/log.py<br/>L6 · rastro de auditoría"]
        FWD["proxy/anthropic_client.py<br/>reenviador upstream"]
    end

    API["api.anthropic.com<br/>(nube — no confiable)"]

    CC -->|petición| PRX
    PRX --> DET --> SEN --> POL --> TRA
    TRA <--> VLT
    TRA -->|MEDIUM/HIGH| LM
    POL --> AUD
    TRA -->|saneado| FWD
    FWD -->|solo lo permitido| API
    API -->|respuesta| FWD
    FWD -->|restaura vía VLT| PRX
    PRX -->|stream| CC

    classDef trusted fill:#e6ffe6,stroke:#2e7d32;
    classDef untrusted fill:#ffe6e6,stroke:#c62828;
    class EXODUS,CC trusted;
    class API untrusted;
```

**Frontera de confianza:** todo lo de la caja verde corre en la máquina del usuario. El nodo rojo es lo único al otro lado de la frontera — y solo recibe lo que la política permitió.

---

## 2. Secuencia de petición (camino feliz)

```mermaid
sequenceDiagram
    participant CC as Claude Code
    participant PX as Proxy Exodus
    participant CL as Clasificador
    participant PO as Política
    participant TR as Transformación (+Bóveda)
    participant LM as Modelo Local
    participant AN as API Anthropic

    CC->>PX: POST /v1/messages (código, archivos, prompt)
    PX->>CL: segmentar + detectar fragmentos
    CL->>PO: fragmentos + etiquetas de sensibilidad
    PO->>TR: decisiones por fragmento
    alt SECRET / HIGH
        TR->>LM: abstraer o manejar localmente
        LM-->>TR: sustituto / resultado local
    end
    TR->>TR: seudonimizar (guardar mapa en la Bóveda)
    TR->>AN: reenviar petición saneada
    AN-->>PX: respuesta en streaming (SSE)
    PX->>TR: restaurar marcadores (desde la Bóveda)
    PX-->>CC: respuesta restaurada en streaming
    PX->>PX: escribir AuditRecord
```

---

## 3. Decisión de enrutado (por fragmento)

```mermaid
flowchart TD
    S["Fragmento"] --> D{"¿Acierto determinista?<br/>(key/token/PII)"}
    D -->|sí: secreto| SEC["SECRET → bloquear / seudonimizar"]
    D -->|sí: PII| LOW["LOW → seudonimizar + reenviar"]
    D -->|no| C{"¿Sensibilidad contextual?"}
    C -->|alta| H["HIGH → solo modelo local"]
    C -->|media| M["MEDIUM → abstraer + reenviar"]
    C -->|baja/desconocida| U{"¿Anulación de política?<br/>(globs, etiquetas)"}
    U -->|coincide sensible| H
    U -->|ninguna| PUB["PUBLIC → reenviar tal cual"]

    classDef stop fill:#ffd6d6,stroke:#c62828;
    classDef warn fill:#fff3cd,stroke:#f9a825;
    classDef ok fill:#d6ffd6,stroke:#2e7d32;
    class SEC,H stop;
    class LOW,M warn;
    class PUB ok;
```

> **Fail-closed:** el camino `desconocida` se inclina hacia la comprobación de política/anulación en vez de caer por defecto a `PUBLIC`.

---

## 4. Vista de despliegue (MVP, en el Mac del usuario)

```mermaid
flowchart LR
    subgraph MAC["MacBook Air M5 · 32 GB (confiable)"]
        CC2["Claude Code CLI"]
        EX["Proxy Exodus<br/>:8787"]
        OL["Ollama<br/>:11434 (modelo local)"]
    end
    NET(["Internet"])
    AN2["API Anthropic"]

    CC2 --> EX
    EX --> OL
    EX --> NET --> AN2
```
