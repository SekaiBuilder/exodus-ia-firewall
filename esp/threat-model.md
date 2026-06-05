# Exodus — Modelo de Amenaza

> **Edición en español.** Espejo de [`docs/threat-model.md`](../docs/threat-model.md). La honestidad es el producto: este documento dice **exactamente** contra qué defiende Exodus y contra qué no. Si una afirmación no se puede defender aquí, no aparece en el README.

## 1. Activos (lo que protegemos)

| Activo | Ejemplos |
|---|---|
| Secretos | API keys, tokens OAuth, claves privadas, valores de `.env`, contraseñas |
| PII | Nombres, emails, teléfonos, direcciones IP, direcciones postales |
| Contenido propietario | Algoritmos secretos, lógica de negocio no publicada, hostnames internos |
| La bóveda | El mapa local marcador ↔ valor real |

## 2. Modelo de adversario

**En alcance — nube honesta-pero-curiosa + economía de datos:**
- Un proveedor de LLM en la nube que recibe, puede registrar, puede retener y puede (según términos) entrenar con las entradas.
- Cadenas de retención/perfilado aguas abajo alimentadas por los datos emitidos.

**Fuera de alcance (explícitamente):**
- Un atacante con **ejecución de código local** en la máquina del usuario (puede leer la bóveda y el texto plano directamente — partida perdida, por construcción).
- Un proveedor **malicioso** que sabotee activamente la inferencia (territorio FHE; ver `FUNDAMENTOS.md` §2.3).
- Canales laterales de **metadatos / temporización de red** (Exodus oculta *contenido*, no el hecho de que hiciste una petición, cuándo, ni de qué tamaño).
- **Re-identificación** de contenido abstraído por un analista determinado.

## 3. Frontera de confianza

```
[ máquina del usuario — CONFIABLE ]  ── salida ──►  [ API de Anthropic — NO CONFIABLE ]
   Claude Code, Exodus, Ollama, bóveda                inferencia en la nube
```

Todo lo anterior a la salida es de confianza. La garantía concierne a **lo que cruza la salida**.

## 4. Garantía de seguridad (lo que Exodus promete)

> Para cualquier fragmento clasificado como `SECRET` o `HIGH` bajo la política activa, el **valor real en texto plano no cruza la frontera de salida**. Los fragmentos `SECRET` se bloquean o seudonimizan; los `HIGH` los maneja el modelo local o se abstraen antes de salir. La bóveda nunca se serializa al cable.

## 5. No-garantías (lo que Exodus NO promete)

1. **Completitud del clasificador.** Un fragmento sensible que el clasificador no detecte (`falso negativo`) **se enviará**. Mitigación: sesgo fail-closed, detectores deterministas para secretos de alto valor, anulaciones de política del usuario, revisión de auditoría.
2. **Tareas dependientes del valor.** Si la tarea necesita el valor real (p. ej. "¿es válida esta API key?"), Exodus no puede a la vez ocultarlo y ayudar.
3. **Anulaciones del usuario.** Si el usuario confirma enviar un fragmento `SECRET`/`HIGH`, es su decisión y sale.
4. **Fuga por abstracción.** El contenido abstraído/minimizado se *reduce*, no se *elimina* — el residuo igual sale.
5. **Metadatos.** La existencia, temporización y tamaño de la petición son visibles para el proveedor.

## 6. Modos de fallo y mitigaciones

| Fallo | Impacto | Mitigación |
|---|---|---|
| Marcador partido entre trozos SSE | Restauración corrupta | Tokens centinela + buffer mínimo |
| Bóveda filtrada a disco/log | Exposición de PII | Bóveda en memoria por defecto; git-ignore; nunca se loguea |
| Falso negativo del clasificador | Fuga | Fail-closed; detectores deterministas de alto valor; tests canario |
| Desajuste de restauración en el bucle de edición | Corrupción de archivo | Marcadores únicos y estables; tests de ida y vuelta |
| Modelo local no disponible | Fragmento `HIGH` no se puede manejar | Bloquear + avisar (nunca reenviar en silencio) |

## 7. Invariantes testeables

- **INV-1:** Ningún valor real `SECRET` aparece en ninguna carga enviada upstream (test canario).
- **INV-2:** La bóveda nunca está presente en ninguna petición saliente ni en ninguna línea de log.
- **INV-3:** Una edición de archivo de ida y vuelta reproduce los valores reales originales byte a byte.
- **INV-4:** Ante fallo del modelo local, los fragmentos `HIGH`/`SECRET` se bloquean, nunca se reenvían.

Estas invariantes son los criterios de aceptación del MVP y la base del arnés de evaluación.
