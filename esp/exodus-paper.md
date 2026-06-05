# Exodus: Enrutado de Privacidad por Sensibilidad para Asistentes de Código Agénticos

> **Edición en español.** Espejo de [`paper/exodus-paper.md`](../paper/exodus-paper.md); para publicación se usa la versión inglesa (estándar académico).

**Autores:** Francesco Catania (@sekaibuilder)
**Estado:** Borrador — abstract e introducción escritos; §3–§7 a rellenar desde implementación y evaluación.
**Artefactos acompañantes:** código (`/src`), fundamentos (`docs/FUNDAMENTOS.md`), modelo de amenaza (`docs/threat-model.md`).

---

## Resumen (Abstract)

Los grandes modelos de lenguaje (LLM) en la nube ofrecen asistencia de vanguardia precisamente porque ingieren contexto de usuario rico —incluyendo código fuente, archivos y datos personales— en infraestructura de terceros. Esto crea una tensión inherente: el mismo contexto que potencia al asistente queda expuesto a retención, entrenamiento y perfilado aguas abajo. Observamos que la forma fuerte del deseo del usuario —*cifrar los datos para que el proveedor no pueda leerlos mientras el modelo sigue usándolos*— es imposible bajo inferencia en la nube, porque el modelo se ejecuta en los servidores del proveedor y por tanto requiere texto plano en el momento de la inferencia; la criptografía no puede ocultar un mensaje de su propio destinatario. Por ello reformulamos el problema como **minimización de datos vía enrutado por sensibilidad**: clasificar el contenido fragmento a fragmento y decidir, por fragmento, si reenviarlo a la nube (opcionalmente seudonimizado o abstraído) o retenerlo en un modelo local. Aunque tal enrutado de privacidad nube–borde es un área de investigación activa, el trabajo previo apunta a prompts genéricos de un solo turno. **Exodus** aplica el enrutado por sensibilidad al **bucle de código agéntico** —preservando uso de herramientas, edición de archivos y streaming de tokens— interponiendo un proxy local compatible con la API de Anthropic delante de Claude Code. Aportamos (i) una implementación open-source por capas, (ii) un modelo de amenaza explícito y testeable con invariantes fail-closed, y (iii) una evaluación reproducible de tasa de fuga, retención de utilidad y sobrecarga de latencia. Exodus se posiciona como un artefacto de ingeniería usable que tiende un puente entre la investigación en privacidad y una herramienta agéntica ampliamente usada, con límites documentados honestamente en vez de garantías falsas.

---

## 1. Introducción

### 1.1 Motivación
Los asistentes de código agénticos como Claude Code han movido los LLM de las cajas de chat al directorio de trabajo del desarrollador: leen archivos, ejecutan herramientas y editan código de forma autónoma. Su utilidad escala con el contexto que se les da, que rutinariamente incluye secretos, información personal identificable (PII) y lógica propietaria. Una vez transmitido, ese contexto sale del control del usuario y entra en una cadena cuyo comportamiento de retención y entrenamiento el usuario rara vez audita y no puede hacer cumplir técnicamente.

### 1.2 La imposibilidad que debemos respetar
Una petición natural es un "ofuscador" que vuelva el contenido del chat indescifrable para el proveedor manteniendo el modelo plenamente funcional. Argumentamos que esto es estructuralmente imposible (Sección 2; ampliado en `FUNDAMENTOS.md` §2): el modelo es un proceso en los servidores del proveedor, así que necesita texto plano en la inferencia; y el proveedor es el *destinatario*, no un *intermediario*, así que el cifrado extremo-a-extremo no aplica. La única vía teórica de escape, el cifrado totalmente homomórfico, es órdenes de magnitud demasiado caro y debe implementarse del lado del proveedor. **La utilidad y la descifrabilidad están en el mismo eje.**

### 1.3 Reformulación: minimizar, no ofuscar
Si el contenido destinado a un modelo que debe entenderlo no puede ocultarse, las palancas accionables son: (1) no enviarlo (cómputo local); (2) enviar un sustituto seudonimizado cuando el *valor* es irrelevante para la tarea; (3) enviar una forma abstraída y reducida; y (4) decidir *por fragmento* cuál palanca aplica. Las palancas (2)–(4) definen el **enrutado por sensibilidad**.

### 1.4 Por qué el escenario agéntico es diferente
Los sistemas de enrutado de privacidad existentes asumen un solo prompt y una sola respuesta. Claude Code viola ambas suposiciones: las respuestas hacen **streaming** (la restauración debe ser segura sobre stream), el cliente **aplica ediciones a archivos reales** (sanear/restaurar debe cuadrar exactamente), y un modelo local pequeño **no puede conducir** el bucle de herramientas (así que localmente debe actuar como pre/post-procesador, no como el agente). Manejar el enrutado por sensibilidad *sin romper el comportamiento agéntico* es, hasta donde sabemos, un problema no abordado.

### 1.5 Aportaciones
1. Un **proxy por capas open-source** que interpone un pipeline de privacidad (detectar → clasificar → política → transformar → enrutar → auditar) entre Claude Code y la API de Anthropic.
2. Un **modelo de amenaza explícito** con invariantes fail-closed testeables (ningún valor `SECRET` cruza la salida; la bóveda nunca se serializa; las ediciones cuadran; fail-closed ante caída local).
3. Una **metodología de evaluación reproducible** para tasa de fuga, retención de utilidad y sobrecarga de latencia.
4. Un **encuadre de honestidad primero**: no-garantías documentadas que previenen la falsa seguridad.

---

## 2. Antecedentes y Trabajo Relacionado

*(Ver `references.bib`.)*

- **Enrutado de privacidad nube–borde.** PRISM enruta por sensibilidad a nivel de entidad con privacidad diferencial local adaptativa y un "boceto semántico" refinado en el borde. PrivacyPAD aprende la delegación vía aprendizaje por refuerzo. Privacy Guard & Token Parsimony descompone prompts y re-enruta sub-tareas de alto riesgo. Exodus se diferencia apuntando al bucle *agéntico* y entregando un artefacto usable en vez de un prototipo de investigación.
- **Anonimización de prompts.** Presidio, LLM-Guard, anonLLM y CleanPrompt proveen detección de PII y (de)anonimización reversible. Exodus reutiliza esta capa (palanca 2) en vez de reinventarla.
- **Ofuscación e inferencia partida.** EmojiPrompt y Hide-and-Seek ofuscan prompts; la inferencia partida divide modelos para que los embeddings queden locales. Los posicionamos frente al compromiso utilidad/descifrabilidad de §1.2.

> **Posicionamiento honesto.** La novedad de Exodus es *aplicación e ingeniería* (agéntico, abierto, con benchmarks, honestamente acotado), **no** un concepto de enrutado nuevo.

## 3. Diseño del Sistema
_[TODO: arquitectura por capas; ampliar desde `docs/ARQUITECTURA.md`.]_

## 4. Implementación
_[TODO: proxy/SSE, detectores, política, bóveda, runtime Ollama; fijar versiones.]_

## 5. Evaluación
_[TODO: tasa de fuga, retención de utilidad, sobrecarga de latencia, curva de compromiso de abstracción; reportar sobre corpus canario + benchmark de código.]_

## 6. Limitaciones y Ética
_[TODO: falsos negativos, canales laterales de metadatos, residuo de abstracción; el deber de no proveer falsa seguridad.]_

## 7. Conclusión
_[TODO]_

## Referencias
Ver `references.bib`.
