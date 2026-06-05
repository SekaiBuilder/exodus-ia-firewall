# Exodus — Estructura del Proyecto (anotada y enumerada)

> **Edición en español.** Espejo de [`docs/ESTRUCTURA.md`](../docs/ESTRUCTURA.md). El "UML textual": cada archivo del repositorio, numerado, con su responsabilidad única.
> Principio: **un módulo, un trabajo.** Un revisor debería predecir el contenido de un archivo a partir de su ruta.

## 0. Árbol del repositorio

```
proyecto-exodus/
├── README.md                      # (1)  Punto de entrada público
├── LICENSE                        # (2)  MIT
├── .gitignore                     # (3)  Ignora secretos, bóveda, cachés
├── pyproject.toml                 # (4)  Empaquetado + dependencias + tooling
├── .env.example                   # (5)  Plantilla de configuración
├── CONTRIBUTING.md                # (6)  Cómo contribuir
├── SECURITY.md                    # (7)  Política y evaluación de seguridad
│
├── docs/                          # documentación canónica (inglés)
├── esp/                           # espejo en español (secundario)
│
├── paper/
│   ├── exodus-paper.md            # (13) Paper académico (abstract + intro escritos)
│   └── references.bib             # (14) Bibliografía / prior art
│
├── src/exodus/
│   ├── __init__.py                # (15) Marcador de paquete + versión
│   ├── proxy/
│   │   ├── server.py              # (16) App FastAPI: reverse-proxy + streaming SSE
│   │   └── anthropic_client.py    # (17) Reenviador upstream a api.anthropic.com
│   ├── classify/
│   │   ├── detectors.py           # (18) Detectores deterministas regex + Presidio
│   │   └── sensitivity.py         # (19) Clasificador de sensibilidad (modelo local)
│   ├── policy/
│   │   ├── policy.py              # (20) Motor de niveles PUBLIC..SECRET
│   │   └── policy.example.yaml    # (21) Plantilla de política declarativa
│   ├── transform/
│   │   ├── pseudonymize.py        # (22) Sustitución reversible + bóveda local
│   │   └── abstract.py            # (23) Abstracción / minimización con modelo local
│   ├── local_model/
│   │   └── runtime.py             # (24) Cliente Ollama (ahora) / MLX (después)
│   ├── audit/
│   │   └── log.py                 # (25) Rastro de auditoría transparente
│   └── cli.py                     # CLI: `exodus serve` / `exodus audit`
│
└── tests/
    ├── test_smoke.py              # (26) Smokes + semilla de canario de fuga
    └── test_proxy.py              # Tests de M1 (passthrough + SSE)
```

## 1. Responsabilidades por capa

El código se organiza como un **pipeline de capas de propósito único**. Los datos bajan en la petición, suben en la respuesta.

| # | Capa | Paquete | Posee | NO debe |
|---|---|---|---|---|
| L0 | **Transporte** | `proxy/` | Hablar la API de Mensajes de Anthropic; streaming SSE; reenvío | Tomar decisiones de privacidad |
| L1 | **Detección** | `classify/detectors.py` | Encontrar secretos/PII de forma determinista | Decidir enrutado |
| L2 | **Clasificación** | `classify/sensitivity.py` | Asignar etiqueta de sensibilidad por fragmento | Mutar contenido |
| L3 | **Política** | `policy/` | Mapear sensibilidad → acción (los niveles) | Detectar o transformar |
| L4 | **Transformación** | `transform/` | Seudonimizar / abstraer; poseer la bóveda | Enrutar o llamar upstream |
| L5 | **Cómputo local** | `local_model/` | Ejecutar el modelo local (clasificar/abstraer) | Saber de HTTP/proxy |
| L6 | **Auditoría** | `audit/` | Registrar qué salió y qué se enmascaró | Alterar la decisión |

**Regla de dependencia:** las capas superiores pueden importar utilidades inferiores, pero `classify/`, `policy/`, `transform/`, `local_model/` y `audit/` deben permanecer **testeables de forma independiente** y libres de imports de `proxy/`. Así el núcleo de privacidad sigue siendo reutilizable por la futura interfaz independiente.

## 2. Contratos de datos (a formalizar en código)

- `Span` — `{text, start, end, kind, sensitivity, source}`
- `PolicyDecision` — `{span, tier, action}` donde action ∈ `{FORWARD, PSEUDONYMIZE, ABSTRACT, LOCAL, BLOCK}`
- `VaultEntry` — `{placeholder, real_value, scope}` (solo local; nunca serializado al cable)
- `AuditRecord` — `{ts, request_id, span_kind, action, backend}`

## 3. Nomenclatura y convenciones

- Python ≥ 3.11, type hints en todo, `ruff` para lint/formato.
- Ningún secreto se loguea en texto plano (los logs de auditoría guardan *tipos*, no valores).
- Los archivos que puedan contener valores reales (`*.vault`, `.env`) están en git-ignore.
