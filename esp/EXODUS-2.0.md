# Exodus 2.0 — El firewall dentro de la caja fuerte (TEE / Intel SGX)

> **Qué es este documento.** La continuación de [FUNDAMENTOS.md](FUNDAMENTOS.md). Exodus 1.x
> resolvió un problema de *software*: enmascarar secretos antes de que viajen a la nube.
> Exodus 2.0 ataca el problema de *hardware* que quedaba abierto: **¿quién protege el vault
> mientras Exodus corre?** Aquí está la teoría, lo que construimos, por qué lo construimos
> así, y cómo comprobamos que funciona. Se puede leer de principio a fin sin haber visto el
> código.

---

## 1. El problema que Exodus 1.x no podía resolver

Repasemos el flujo de Exodus 1.x:

```
Claude Code ──► Exodus (localhost) ──► api.anthropic.com
                  │
                  └─ vault en memoria: { ⟪EXODUS:credit_card:1⟫ → "4242 4242 4242 4242" }
```

El vault guarda los valores reales para restaurarlos en la respuesta. Mientras Exodus corre
en **tu** máquina, ese vault vive en **tu** memoria y el riesgo es aceptable. Pero piensa en
los despliegues que importan de verdad:

- Exodus corriendo en un servidor compartido de una empresa.
- Exodus como *gateway* de privacidad para un equipo entero, en una VM en la nube.
- Un agente de IA remoto que quiere usar un Exodus que **no** está en su máquina.

En todos esos casos aparece el mismo atacante nuevo: **el operador de la máquina**. Quien
tenga root en ese servidor puede leer la memoria del proceso (`/proc/PID/mem`, un volcado de
memoria, un depurador) y llevarse el vault con todos los secretos en claro. Ningún firewall
de software se defiende de root. Ese es exactamente el límite que el modelo de amenaza de
Exodus 1.x declaraba honestamente como "fuera de alcance".

**Exodus 2.0 = cerrar ese hueco con hardware.**

---

## 2. Teoría: qué es un TEE y por qué root no puede mirar dentro

### 2.1 La idea en una frase

Un **TEE** (*Trusted Execution Environment*) es una zona del procesador donde el código corre
con la memoria **cifrada por el propio chip**, con una clave que nunca sale del silicio. El
sistema operativo, el hipervisor y el administrador ven solo bytes cifrados.

### 2.2 Intel SGX en concreto

**SGX** (*Software Guard Extensions*) es la implementación de Intel. Crea **enclaves**:
regiones de memoria protegidas donde:

1. **La RAM del enclave está cifrada.** El controlador de memoria del CPU cifra/descifra al
   vuelo. Un volcado físico de la RAM, o root leyendo `/proc/PID/mem`, obtiene ruido.
2. **Ni el kernel puede entrar.** Las instrucciones de acceso al enclave las controla el CPU.
   Un sistema operativo malicioso puede *matar* el enclave (denegación de servicio), pero no
   *leerlo*.
3. **El enclave puede demostrar quién es.** El CPU mide el código cargado (hash llamado
   **MRENCLAVE**) y puede firmar esa medida con claves fundidas en el chip. Esto se llama
   **attestation** y es la pieza que convierte "confía en mí" en "verifícame" (sección 5).

La consecuencia práctica para Exodus: **el vault dentro de un enclave SGX es ilegible incluso
para el administrador de la máquina donde corre.**

### 2.3 Lo que un TEE NO da (honestidad primero)

- No oculta que el proceso existe, ni cuándo se comunica, ni con quién (metadatos).
- No protege contra bugs *dentro* del enclave: si Exodus tuviera una vulnerabilidad, el
  enclave la ejecuta fielmente. El hardware protege el perímetro, no el contenido.
- Los canales laterales (timing, caché) son un área de investigación activa; SGX ha tenido
  CVEs históricos. "Mucho más difícil" ≠ "imposible".
- El prompt sigue llegando al proveedor del modelo: el TEE protege el **vault y el proceso**,
  no cambia la imposibilidad fundamental de la sección 2 de FUNDAMENTOS.

---

## 3. Gramine: meter Python en un enclave sin reescribir nada

### 3.1 El problema de ingeniería

SGX ejecuta código nativo dentro del enclave, pero un proceso normal hace *syscalls* (abrir
archivos, sockets…) que el enclave no puede hacer directamente. Reescribir Exodus para SGX
nativo sería un proyecto de meses.

### 3.2 La solución: una LibOS

**Gramine** es una *library OS*: una capa que corre **dentro** del enclave y emula Linux para
la aplicación. Python cree estar en Linux normal; Gramine intercepta las syscalls y decide
qué puede salir del enclave y qué no. Resultado: **Exodus corre sin cambiar una línea de
código**. Solo hace falta un **manifiesto** que declara el mundo visible desde dentro.

### 3.3 El manifiesto, explicado línea a línea

El archivo real es [`exodus.manifest.template`](../exodus.manifest.template). Sus piezas:

```toml
loader.entrypoint = {uri = "file:{{ gramine.libos }}"}   # la LibOS que arranca dentro
libos.entrypoint = "/usr/bin/python3.12"                  # el binario que ejecuta
loader.argv = ["/usr/bin/python3.12", ".../exodus", "serve"]

loader.env.LD_LIBRARY_PATH = "/lib:..."   # dónde busca libc el linker DENTRO del enclave
loader.env.PYTHONPATH = "..."             # dónde están exodus y sus dependencias

fs.mounts = [ ... ]          # qué directorios del host son visibles dentro (y nada más)
sgx.allowed_files = [ ... ]  # qué archivos pueden abrirse (lista blanca explícita)
```

Dos modos de ejecución, **mismo manifiesto**:

| Comando | Qué hace | Protección |
|---|---|---|
| `gramine-direct` | LibOS sin enclave (simulación funcional) | ninguna — para desarrollo |
| `gramine-sgx` | LibOS dentro de enclave SGX real | total — requiere CPU con SGX |

Esta es la decisión de diseño clave del proyecto: **desarrollar todo en simulación** (que
corre en cualquier Linux x86_64, incluso GitHub Codespaces gratis) sabiendo que el paso a
hardware real es cambiar un comando.

### 3.4 Las tres lecciones que costaron horas (para no repetirlas)

Documentamos los errores reales del proceso porque son los que cualquier replicador sufrirá:

1. **`sgx.allowed_files` también aplica en modo direct.** El error `Permission denied
   (EACCES)` en `libos_init` no era de permisos Unix: Gramine bloquea *todo* archivo no
   listado. La pista estaba en `loader.log_level = "trace"`:
   `Disallowing access to file 'hello_static'; file is not allowed.`
2. **El linker dentro del enclave no encuentra libc sin ayuda.** Gramine monta su propia
   glibc parcheada en `/lib`, pero el loader dinámico buscaba en las rutas del host. La
   solución es `loader.env.LD_LIBRARY_PATH = "/lib:..."` apuntando al mount interno.
3. **Gramine no sigue symlinks como esperarías.** `/usr/bin/python3` → `python3.12` fallaba;
   hay que apuntar `libos.entrypoint` al binario real.

### 3.5 Cómo sabemos que funciona

Secuencia de validación que ejecutamos, de menor a mayor complejidad (cada paso aísla una
capa):

1. **Binario estático C** (`hello_static`) → valida manifiesto y LibOS, sin linker dinámico.
2. **`/bin/sh` dinámico** → valida linker + libc dentro del enclave.
3. **Python + script** → valida el runtime completo de CPython.
4. **`exodus selftest`** → los 26 detectores del firewall, dentro del enclave:
   `PASS 23/23 protected values masked and restored exactly · 0 leaked to egress`.
5. **`exodus serve`** → uvicorn + FastAPI sirviendo en `:8787` desde dentro; peticiones
   reales desde fuera (`curl /_exodus/health` → `200 OK`).

---

## 4. Attestation: de "confía en mí" a "verifícame"

### 4.1 El problema

Un servidor te dice: "tranquilo, corro dentro de un enclave". ¿Por qué le creerías? Las
palabras no cuestan nada. Attestation es la respuesta criptográfica.

### 4.2 Cómo funciona el protocolo (implementado en `src/exodus/attest.py`)

```
verificador                                 enclave
───────────                                 ───────
1. genera nonce aleatorio fresco
2. GET /_exodus/attest?nonce=N  ──────────►
                                            3. report_data = sha256(N)   (64 bytes)
                                            4. escribe report_data en
                                               /dev/attestation/user_report_data
                                            5. lee /dev/attestation/quote
                                               → el CPU firma: MRENCLAVE + report_data
◄────────────── { quote, report_data } ────
6. comprueba: ¿el quote contiene sha256(N)?     → frescura (no es una respuesta grabada)
7. comprueba: ¿MRENCLAVE == build esperado?     → es EXACTAMENTE nuestro código
8. (producción) valida la firma con la CA de Intel → es un chip SGX genuino
```

Conceptos clave:

- **Nonce** → impide *replay*: un atacante no puede reutilizar una attestation vieja porque
  cada verificación exige un quote sobre un nonce nuevo.
- **MRENCLAVE** → hash del código cargado en el enclave. Si alguien modifica Exodus (p.ej.
  para exfiltrar el vault), el MRENCLAVE cambia y el verificador lo rechaza. Por eso se
  "fija" (*pinning*): `exodus verify --mrenclave <hash-del-build-auditado>`.
- **Quote** → la estructura firmada por el CPU. Nuestro parser extrae MRENCLAVE (offset 112),
  MRSIGNER (offset 176) y report_data (offset 368) del cuerpo del informe SGX.

### 4.3 La decisión de diseño: simulación etiquetada

Sin hardware SGX no hay quote real. En vez de fingirlo, el endpoint devuelve el **mismo
esquema JSON** con `"simulated": true` y sin quote. El verificador lo **rechaza por defecto**
(`VERDICT: NOT TRUSTED`, exit 1) salvo que se pase `--allow-simulated`. Esto permite
desarrollar y testear todo el protocolo hoy, sin mentir sobre las garantías. Cuando llegue el
hardware, el mismo código produce y verifica quotes reales.

### 4.4 Cómo sabemos que funciona

- 8 tests unitarios del verificador (`tests/test_verify.py`): replay rechazado, quote
  sintético válido aceptado, MRENCLAVE equivocado rechazado, quote truncado rechazado.
- Prueba end-to-end real: servidor vivo + `exodus verify` → los ✓ de nonce y report_data, y
  el verdict correcto en ambos modos (estricto y permisivo).

---

## 5. RA-TLS: atar el canal cifrado al enclave

### 5.1 El ataque que faltaba por cubrir

Attestation dice "ese enclave es genuino". TLS dice "este canal es cifrado". Pero, ¿y si el
TLS termina **fuera** del enclave (un proxy malicioso en medio) que reenvía la attestation
del enclave real? Verías ✓ en attestation y ✓ en TLS… y tus secretos pasarían en claro por
el atacante.

### 5.2 La solución (patrón RA-TLS, implementado en `src/exodus/tlsbind.py`)

Ligar las dos cosas: el `report_data` deja de comprometer solo el nonce y pasa a comprometer
**nonce + huella del certificado TLS**:

```
report_data = sha256( nonce | sha256(certificado_DER) )
```

El verificador (1) se conecta por TLS, (2) captura el certificado que *él* está viendo,
(3) exige que la attestation comprometa exactamente esa huella. Un hombre-en-el-medio
presenta su propio certificado → la huella no coincide → `NOT TRUSTED`.

Detalle elegante: el certificado es **autofirmado a propósito**. No hace falta una CA — la
confianza viene del silicio, no de una autoridad. Una CA puede certificar identidad; no puede
certificar "este canal termina dentro de un enclave". La attestation sí.

```bash
exodus serve --tls                              # genera cert, ata su huella al report_data
exodus verify --url https://host:8787 ...       # captura el cert y exige la atadura
```

### 5.3 Cómo sabemos que funciona

- 3 tests de binding: documento sin binding rechazado cuando el verificador vio un cert,
  binding correcto aceptado, binding ajeno rechazado.
- End-to-end real con HTTPS vivo:
  `✓ TLS certificate fingerprint bound into attestation` ·
  `✓ report_data == sha256(nonce|tls-cert)` · `VERDICT: TRUSTED`.

---

## 6. MCP: el enclave como servicio para agentes

### 6.1 Por qué esto cierra el círculo

La literatura reciente sobre *Confidential Computing for Agentic AI* propone que los agentes
de IA deleguen secretos solo en infraestructura **verificable**. Eso exige dos piezas: un
gateway que pueda probar dónde corre (secciones 4–5) y un **protocolo por el que un agente
pregunte**. Esa segunda pieza es MCP (*Model Context Protocol*), el estándar de tools para
agentes.

### 6.2 Qué implementamos (`src/exodus/mcp_server.py`)

`exodus mcp` — servidor MCP por stdio (JSON-RPC 2.0, líneas de JSON). Sin SDK externo: la
superficie necesaria (initialize, tools/list, tools/call, ping) son ~170 líneas legibles.

| Tool | Para qué la usa un agente |
|---|---|
| `exodus_mask` | "enmascárame este texto antes de que salga a cualquier sitio" |
| `exodus_verify` | "¿puedo fiarme de ese gateway de privacidad?" — attestation desde el loop del agente |
| `exodus_audit` | "¿qué se ha enmascarado hasta ahora?" (tipos y conteos, nunca valores) |

Registro en Claude Code: `claude mcp add exodus -- exodus mcp`.

### 6.3 Cómo sabemos que funciona

- 7 tests de protocolo (`tests/test_mcp.py`): handshake, lista de tools, dispatch, errores
  JSON-RPC correctos (-32601/-32602), fallos de tool como `isError` (según spec MCP).
- Sesión stdio real: `exodus_mask` enmascaró en vivo una tarjeta y una API key de Anthropic:
  `"my card ⟪EXODUS:credit_card:1⟫ and token ⟪EXODUS:anthropic_key:2⟫"`.

---

## 7. Tutorial completo: reproducir todo desde cero

Necesitas cualquier Linux x86_64 (un GitHub Codespace de 4 cores sirve; SGX **no** es
necesario para la simulación).

```bash
# 1. Gramine (Ubuntu 24.04 "noble")
echo "deb [arch=amd64 trusted=yes] https://packages.gramineproject.io/ noble main" \
  | sudo tee /etc/apt/sources.list.d/gramine.list
sudo apt update && sudo apt install -y gramine
gramine-direct --version          # → Gramine 1.9

# 2. Exodus
git clone https://github.com/SekaiBuilder/exodus-ia-firewall && cd exodus-ia-firewall
pip install -e .

# 3. Compilar el manifiesto y arrancar dentro de la LibOS
gramine-manifest -Darch_libdir=/lib/x86_64-linux-gnu \
    exodus.manifest.template exodus.manifest
gramine-direct exodus             # banner de Exodus servido desde dentro

# 4. (otra terminal) el ciclo completo de confianza
curl -s http://127.0.0.1:8787/_exodus/health      # → {"status":"ok"}
exodus verify --allow-simulated                    # → VERDICT: TRUSTED (simulado)
exodus verify                                      # → NOT TRUSTED, exit 1 (estricto)

# 5. Canal atado al enclave (RA-TLS)
exodus serve --tls                                 # en la terminal 1
exodus verify --url https://127.0.0.1:8787 --allow-simulated

# 6. Tools para agentes
claude mcp add exodus -- exodus mcp

# 7. Suite completa
pip install -e ".[dev]" && pytest                  # 73 passing
```

**En hardware SGX real** (Azure DCsv3, Xeon con SGX): los pasos son idénticos cambiando
`gramine-direct` por `gramine-sgx`; `/_exodus/attest` pasa a devolver quotes de hardware y
`exodus verify --mrenclave <hex>` da garantías reales.

---

## 8. Estado, límites y siguiente paso

### Hecho y verificado (73 tests)

- Exodus completo (26 detectores, proxy, vault) corriendo bajo Gramine LibOS.
- Protocolo de attestation con frescura por nonce y pinning de MRENCLAVE.
- Canal TLS criptográficamente atado a la attestation (RA-TLS).
- Servidor MCP: el enclave como servicio verificable para agentes.

### Pendiente (requiere CPU con SGX)

- Ejecutar con `gramine-sgx` y obtener quotes de hardware reales (las suscripciones cloud
  de estudiante no incluyen las familias DC*; alternativas: ticket de cuota a Azure, o un
  Xeon Ice Lake+ con SGX habilitado).
- Demostrar empíricamente que el vault es ilegible desde el host (leer `/proc/PID/mem` del
  enclave y mostrar el fallo).
- *Sealing*: persistir el vault cifrado con la clave del enclave (en Gramine, mounts de tipo
  `encrypted`), para que sobreviva reinicios sin tocar disco en claro.
- Validación completa de la cadena de firma DCAP (QVL/PCCS de Intel) en el verificador.

### La tesis de Exodus 2.0, en una frase

> Exodus 1.x protege tus secretos **del modelo**; Exodus 2.0 los protege además **de la
> máquina donde corre Exodus** — y lo convierte en algo que un agente puede **verificar**
> en vez de creer.
