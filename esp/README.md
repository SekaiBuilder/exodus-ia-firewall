# Exodus 🛡️

> Un **enrutador de privacidad local y consciente de la sensibilidad** para clientes LLM
> agénticos — Claude Code y Codex.

**Licencia:** MIT · **Estado:** funcional (M0–M4 · 46 tests en verde) · **Idioma:** la versión
**canónica es la inglesa** → [`README.md`](../README.md).

Exodus corre en tu propia máquina, entre tu agente de IA y la API en la nube, y **minimiza
los datos sensibles que salen** — enmascara secretos y PII *antes* de enviarlos, y los
restaura de forma transparente en la respuesta para que tus herramientas sigan funcionando.

---

## ⚠️ Alcance honesto (léelo primero)

Exodus es **reducción de daño, no invisibilidad.** No vende una promesa imposible.

- El modelo corre **en los servidores del proveedor**, así que tu prompt *tiene* que llegar
  para que la IA responda. Exodus no lo hace invisible — **quita las partes sensibles antes
  de que viajen**.
- Enmascara lo que **reconoce**: secretos con firma (`sk-ant-…`, `AKIA…`, JWTs…) y PII
  estructurada que **valida** (tarjetas por Luhn, IBAN por mod-97, DNI/NIE, SSN). Una cadena
  aleatoria sin firma *no* es detectable como secreto.
- **No** oculta tu identidad/metadatos — el proveedor sigue sabiendo que es tu cuenta.
- La capa de modelo local (M4) es **con pérdida**: quita identificadores del texto libre,
  pero el sentido general sigue saliendo.
- **Apps GUI de consumidor (Claude Desktop, ChatGPT) quedan fuera** — Exodus protege el
  *bucle agéntico / de API* (CLIs, SDKs), la superficie de alto riesgo.

Modelo de amenaza completo: [`threat-model.md`](threat-model.md).

---

## Cómo se usa

```bash
# Instalar (en un venv)
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                 # firewall núcleo — sin modelo, sin Ollama
pip install -e ".[local]"        # opcional: modelo local embebido (capa M4)

# Arrancar
exodus serve                     # escucha en http://127.0.0.1:8787
```

**Claude Code (Anthropic)** — en la terminal, exporta **antes** de lanzar:
```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
claude
```

**Codex (OpenAI)** — una 2ª instancia hacia OpenAI, en otro puerto:
```bash
EXODUS_UPSTREAM=https://api.openai.com EXODUS_PORT=8788 exodus serve
```
y apunta `~/.codex/config.toml` con `base_url = "http://127.0.0.1:8788/v1"`.

**Ver qué salió de verdad:**
```bash
exodus audit                     # tipos + acciones enmascaradas — nunca los valores
```

---

## Qué detecta

- **Secretos** (siempre enmascarados): Anthropic · OpenAI · AWS · Google · GitHub · Slack ·
  Stripe · SendGrid · npm · JWT · claves PEM · Bearer · URIs de BD con credenciales.
- **PII estructurada validada** (enmascarada por defecto): tarjetas (Luhn) · IBAN (mod-97) ·
  DNI/NIE · SSN.
- **PII de contacto** (detectada, opt-in): email · IPv4 · teléfono internacional.
- **Texto libre** (nombres, direcciones, cualquier idioma) → la **capa de modelo local** (M4).

---

## Modelo local (M4, opcional)

Para contenido sensible *sin firma*, Exodus corre un modelo pequeño **embebido en el proceso**
(llama.cpp + GGUF — **sin Ollama**), que clasifica y abstrae en local. Apagado por defecto.

```bash
pip install -e ".[local]"
EXODUS_LOCAL_MODEL=on exodus serve   # descarga un modelo pequeño una vez, luego offline
```

Ejemplo — el modelo quita identificadores y conserva la idea:
```
in:  Paciente John Smith, 47, historial #55231, Calle Roble 12, Madrid, tiene asma.
out: Un paciente tiene asma.
```

---

## Documentación
Fundamentos: [`FUNDAMENTOS.md`](FUNDAMENTOS.md) · Arquitectura: [`ARQUITECTURA.md`](ARQUITECTURA.md)
· Estructura: [`ESTRUCTURA.md`](ESTRUCTURA.md) · Amenazas: [`threat-model.md`](threat-model.md)
· **README principal (inglés):** [`../README.md`](../README.md) · Seguridad: [`../SECURITY.md`](../SECURITY.md)

## Licencia
MIT © Francesco Catania (@sekaibuilder). Ver [`../LICENSE`](../LICENSE).

## Aviso
Exodus es una herramienta de **reducción de daño**, no una garantía de anonimato. Reduce los
datos sensibles que llegan a servidores de terceros; no te vuelve invisible.
