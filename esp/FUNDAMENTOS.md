# Exodus — Fundamentos teóricos y prácticos

> **Edición en español.** Espejo de [`docs/FUNDAMENTOS.md`](../docs/FUNDAMENTOS.md); la versión canónica es la inglesa.
>
> **Propósito.** Esta es la base de conocimiento del proyecto: teoría, práctica, modelo de amenaza, estado del arte y plan de evaluación. Está escrita para que el paper académico (`paper/exodus-paper.md`) pueda ensamblarse a partir de ella. Mantenerla rigurosa y honesta — cualquier afirmación aquí puede acabar en un sitio revisado por pares.

**Mantenido por:** Francesco Catania (@sekaibuilder)
**Estado:** en funcionamiento — hitos M0–M4 completos.

---

## 1. Planteamiento del problema y motivación

Los asistentes LLM modernos son potentes precisamente porque ingieren contexto rico: código fuente, archivos, salida de terminal, notas personales. Esa misma riqueza es un riesgo de privacidad:

1. **Exposición.** Todo lo que se envía a un modelo en la nube se procesa en infraestructura de terceros.
2. **Retención y entrenamiento.** Según los términos del proveedor, las entradas pueden retenerse o usarse para mejorar modelos. (Los términos comerciales/API suelen excluir el entrenamiento por defecto; los de consumidor difieren y cambian.)
3. **Externalidades de perfilado.** La economía de datos en general convierte el rastro de comportamiento en perfiles. Reducir lo que emites es una forma de autonomía.

**Objetivo de Exodus:** minimizar los datos sensibles que llegan a servidores de terceros **sin destruir la utilidad** del asistente, y **sin exagerar** la protección ofrecida.

---

## 2. La imposibilidad fundamental (y lo que SÍ es posible)

### 2.1 No puedes ocultar un mensaje de su propio destinatario

Una intuición común es: "cifra el chat para que el proveedor no pueda descifrarlo, pero que el modelo siga funcionando". Esto es **imposible** con la arquitectura actual de inferencia en la nube, por una razón estructural:

> El modelo es un programa **que corre en los servidores del proveedor**. Para que entienda el texto, el texto plano (o una representación semánticamente equivalente) debe existir en la ventana de contexto **en el momento de la inferencia**, en ese servidor. Cifrar el contenido frente al servidor lo cifra también frente al modelo.

La criptografía oculta mensajes de un **tercero en el canal** (un espía), **no del destinatario**. El proveedor no es el espía aquí — es el destinatario (el modelo es la parte con la que te comunicas). No puedes pactar una clave "con el modelo" que el proveedor no tenga, porque la infraestructura del proveedor ejecuta el lado del modelo de esa clave.

### 2.2 Utilidad y descifrabilidad son el mismo eje

No existe una codificación que sea a la vez (a) lo bastante estructurada para que el modelo en la nube razone sobre ella y (b) opaca para el servidor. Cuanto más "razonable" sea la entrada, más recuperable es su significado del lado del servidor — porque la comprensión del propio modelo es un cómputo del lado del servidor (observable en activaciones y salidas). El cifrado fuerte convierte la entrada en ruido de alta entropía que el modelo no puede usar.

### 2.3 La única excepción teórica: FHE — y por qué queda fuera de alcance

El **Cifrado Totalmente Homomórfico (FHE)** permite computar sobre texto cifrado sin descifrarlo; en principio un modelo podría correr bajo FHE y el servidor nunca vería texto plano. En la práctica:

- Multiplica el cómputo por **órdenes de magnitud** (miles–millones×), violando cualquier restricción de latencia/coste.
- Debe implementarlo **el proveedor** en su motor de inferencia; no se puede añadir desde el cliente.
- Ningún modelo de frontera en producción lo ofrece.

Se reconoce FHE por completitud y queda **explícitamente fuera de alcance** para Exodus.

### 2.4 Corolario: las únicas palancas reales

Si no puedes ocultar contenido a un modelo que debe entenderlo, las palancas que quedan son:

1. **No enviarlo** — mantener el cómputo local (autoalojamiento total).
2. **Enviar un sustituto saneado** — seudonimizar valores cuyo *significado es irrelevante* para la tarea.
3. **Enviar una forma reducida** — abstraer/minimizar el contenido para exponer menos.
4. **Decidir por fragmento** cuál de las anteriores aplicar — *enrutado por sensibilidad*.

Exodus se construye sobre las palancas 2–4, con la palanca 1 disponible para los fragmentos más sensibles.

---

## 3. El espectro de soluciones

| Enfoque | Privacidad | Utilidad | Hardware | Notas |
|---|---|---|---|---|
| **Solo nube** | Ninguna | Máxima | Ninguno | Statu quo |
| **Proxy de seudonimización** | Oculta valores marcados | Alta | Ligero | Técnica conocida; solo datos de valor irrelevante |
| **Abstracción local** | Reduce identificabilidad | Media–Alta | Ligero–Medio | Con pérdida; los hechos abstraídos igual salen |
| **Enrutado por sensibilidad (Exodus)** | Graduada, por fragmento | Alta (ajustable) | Ligero–Medio | Combina lo anterior con política + respaldo local |
| **Autoalojamiento total** | Máxima | Limitada por el modelo local | Pesado | Los datos nunca salen; modelo más débil |

---

## 4. Conceptos núcleo

### 4.1 Detección
- **Detectores deterministas:** regex + patrones curados para secretos (API keys, tokens, claves privadas) y PII estructurada (emails, IPs, rutas). Alta precisión, rápido, solo CPU.
- **Detección contextual:** un modelo local pequeño (tipo NER o prompt de clasificación) para entidades que necesitan contexto (nombres de persona, identificadores propietarios).

### 4.2 Clasificación de sensibilidad
Cada **fragmento (span)** (frase, bloque de código, entidad) recibe una etiqueta de sensibilidad. Entradas del clasificador:
- aciertos de los detectores deterministas,
- salida del modelo contextual,
- **política del usuario** (palabras clave, globs de archivos, etiquetas de proyecto — p. ej. "todo bajo `/secret/` es máximo").

**Regla de diseño — fail-closed:** ante la duda, tratar un fragmento como *más* sensible, no menos.

### 4.3 Niveles de política
| Nivel | Acción |
|---|---|
| `PUBLIC` | reenviar tal cual |
| `LOW` | reenviar, seudonimizado |
| `MEDIUM` | reenviar, seudonimizado **+ abstraído** |
| `HIGH` | **solo modelo local** |
| `SECRET` | bloquear / requerir anulación explícita del usuario |

La política es del usuario y declarativa (`policy.example.yaml`).

### 4.4 Seudonimización reversible
Los valores sensibles se reemplazan por **marcadores únicos y estables**; el mapeo (la *bóveda*) **nunca sale de la máquina**. En el camino de respuesta, los marcadores se restauran a los valores reales localmente. Crítico para clientes agénticos: las ediciones de archivos solo cuadran si la restauración es exacta.

### 4.5 Abstracción / minimización local
Un modelo local reescribe un fragmento sensible en una forma menos identificable pero aún útil (p. ej. un expediente médico exacto → "adulto con diabetes tipo 2, sin problemas renales"). **Con pérdida y honesto:** los hechos abstraídos igual salen de la máquina; esto reduce, no elimina, la exposición.

### 4.6 Enrutado por sensibilidad
El despachador envía cada fragmento a su backend elegido por política (nube vs. local) y luego **fusiona** los resultados. Es el centro de gravedad del proyecto y su problema de ingeniería más difícil (ver §6).

---

## 5. La complicación agéntica (por qué Claude Code es especial)

La literatura de investigación apunta a *prompts genéricos de un solo turno*. Claude Code es **agéntico**: lee archivos, los escribe, invoca herramientas y hace streaming. Esto rompe el enrutado ingenuo:

1. **Streaming (SSE).** Las respuestas llegan en trozos; la restauración debe ocurrir sobre un flujo de tokens sin partir marcadores entre fronteras de trozo.
2. **El bucle de edición.** El cliente aplica las ediciones devueltas a archivos reales. Sanear-al-enviar **debe** ir emparejado con restaurar-al-recibir de forma exacta, o las ediciones corrompen archivos.
3. **El modelo local ≠ agente.** Un modelo local pequeño es malo manejando bucles de herramientas. Por tanto, *dentro de Claude Code*, el modelo local actúa como **pre/post-procesador** (clasificar, abstraer, seudonimizar) — **no** como el agente que responde los turnos de herramientas. La rama "el modelo local responde el turno entero" se reserva para una futura interfaz independiente donde controlemos el bucle.

Este encuadre agéntico es el nicho defendible de Exodus: **aplicar enrutado por sensibilidad preservando tool-use, edición de archivos y streaming.**

---

## 6. Problemas abiertos / preguntas de investigación

1. **Precisión de clasificación bajo sesgo fail-closed** — minimizar fugas (falsos negativos) sin lisiar la utilidad (falsos positivos).
2. **Restauración segura sobre stream** — restauración de marcadores demostrablemente correcta sobre SSE en trozos.
3. **Coherencia de la fusión** — coser salidas local + nube en una sola respuesta agéntica coherente (la frontera de V2; cf. split/merge en Privacy Guard, PRISM).
4. **Fidelidad de la abstracción vs. exposición** — cuantificar el equilibrio privacidad/utilidad de la abstracción local.

---

## 7. Modelo de amenaza (resumen)

Ver `docs/threat-model.md` para la versión completa.

- **Activos:** secretos, PII, código/lógica propietaria, la bóveda local.
- **Adversario:** un proveedor de nube honesto-pero-curioso + la cadena de retención/entrenamiento/perfilado; *no* un Estado-nación con compromiso del host local.
- **Frontera de confianza:** la máquina del usuario es de confianza; todo lo que pasa de la salida del proxy es no confiable.
- **Garantía:** los fragmentos sensibles marcados (según política) no cruzan la frontera en texto plano.
- **No-garantías explícitas:** fragmentos mal clasificados; tareas que dependen del valor real; cualquier cosa que el usuario anule; metadatos/temporización.

---

## 8. Plan de evaluación (métricas)

Para que las afirmaciones sean publicables, Exodus debe medirse, no afirmarse:

- **Tasa de fuga** — fracción de secretos/PII "canario" inyectados que llegan al endpoint (simulado) de la nube. Meta: → 0 en `SECRET`/`HIGH`.
- **Retención de utilidad** — éxito de tarea en un benchmark de código *con* vs *sin* Exodus.
- **Sobrecarga de latencia** — latencia añadida por petición (clasificación + transformación + restauración).
- **Curva de compromiso de abstracción** — exposición vs. utilidad en función de la agresividad del nivel.

Un arnés reproducible vive en `tests/` y (más adelante) `benchmarks/`.

---

## 9. Glosario

- **Fragmento (span)** — unidad de contenido clasificada de forma independiente (entidad, frase, bloque de código).
- **Bóveda (vault)** — el mapa local, nunca exportado, de marcador ↔ valor real.
- **Fail-closed** — ante la incertidumbre, elegir la acción más privada.
- **Sustituto (surrogate)** — el marcador/valor abstraído enviado en lugar del real.

## 10. Referencias

La bibliografía (PRISM, PrivacyPAD, Privacy Guard, LLM-Guard, Presidio, FHE, etc.) se mantiene en `paper/references.bib`.
