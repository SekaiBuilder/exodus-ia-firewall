# Running Exodus on real Intel SGX hardware

This is the operational runbook for taking Exodus from the **simulated** attestation flow
(which runs on any machine) to a **real hardware quote** on an Intel SGX CPU. The end result:
`exodus verify` passes in **strict mode** against a remote enclave, pinned to a known
`MRENCLAVE`.

You do **not** need Intel's developer cloud or a corporate account. Any Ubuntu 24.04 box with
an SGX-capable CPU works — `scripts/provision-sgx-server.sh` installs the whole stack.

---

## 0 · What you need

- A Linux host with **Intel SGX** (Coffee Lake / Ice Lake-SP or newer) and SGX **enabled in
  BIOS**. On a cloud VM the provider handles the BIOS.
- Ubuntu 24.04 (noble) on that host.
- SSH access to it.

**Recommended cloud VM (personal account, pay-as-you-go):**

| Provider | Size | SGX | Rough cost |
|---|---|---|---|
| Azure Confidential Computing | `Standard_DC1s_v3` | yes (Ice Lake) | ~$0.10–0.15 / hour |
| Alibaba Cloud | `g7t` (security-enhanced) | yes | similar |

A single evening on a `DC1s_v3` is enough to provision, capture the quote, and shut it down.
Use **pay-as-you-go**, not an Azure for Students subscription (those have a 0 quota on the DC
family).

---

## 1 · Create the VM (Azure example)

Portal: *Create a resource → Virtual machine → Image: Ubuntu Server 24.04 LTS → Size: see the
"Confidential compute" family → `DC1s_v3`*. If the size is greyed out, the region is out of
capacity — try another (East US, North Europe, UK South are common) or open a quota request
for the `DCSv3` family.

Or with the Azure CLI:

```bash
az group create -n exodus-sgx -l northeurope
az vm create \
  -g exodus-sgx -n exodus-sgx \
  --image Canonical:ubuntu-24_04-lts:server:latest \
  --size Standard_DC1s_v3 \
  --admin-username azureuser --generate-ssh-keys
az vm open-port -g exodus-sgx -n exodus-sgx --port 8787
```

> **Delete it when you're done:** `az group delete -n exodus-sgx --yes --no-wait`.

---

## 2 · Provision the host

SSH in and run the one-shot script straight from the repo:

```bash
ssh azureuser@<VM_PUBLIC_IP>
curl -fsSL https://raw.githubusercontent.com/SekaiBuilder/exodus-ia-firewall/main/scripts/provision-sgx-server.sh -o provision.sh
bash provision.sh
```

It installs the Intel DCAP stack, Gramine, clones Exodus into a venv, writes the server
manifest, signs it, and prints the next command. Confirm SGX is actually present:

```bash
ls -l /dev/sgx_enclave /dev/sgx_provision   # both must exist
grep -c sgx /proc/cpuinfo                    # must be > 0
is-sgx-available                             # ships with Gramine; should report SGX usable
```

If `/dev/sgx_*` is missing, SGX is off in BIOS (bare metal) or the VM size has no SGX.

---

## 3 · Note the MRENCLAVE, then launch the enclave

The signing step in the script already printed the enclave measurement. To read it again:

```bash
cd ~/exodus-ia-firewall
gramine-sgx-sign --manifest exodus.manifest --output exodus.manifest.sgx --verbose 2>&1 \
  | grep -i mr_enclave
```

Copy that hex — it is the **MRENCLAVE** you will pin. Then start Exodus inside the enclave:

```bash
gramine-sgx exodus        # serves on 0.0.0.0:8787, vault sealed inside the enclave
```

---

## 4 · Verify from your laptop (strict mode)

From your Mac, point `exodus verify` at the remote enclave. **No `--allow-simulated`** this
time — that is the whole point:

```bash
# Should now return a HARDWARE quote, not simulated:
curl -s "http://<VM_PUBLIC_IP>:8787/_exodus/attest?nonce=$(openssl rand -hex 8)" | python3 -m json.tool

# Strict verification, pinned to the exact build you signed:
exodus verify --url http://<VM_PUBLIC_IP>:8787 --mrenclave <MR_ENCLAVE_HEX>
```

Expected: `attestation_type` is no longer `unavailable`, `simulated` is gone/false, and the
verdict is **TRUSTED**. A wrong `--mrenclave` must print **NOT TRUSTED** (exit 1) — try it once
on purpose so you've seen the failure path.

For the channel-bound form, run `gramine-sgx exodus` with `--tls` on the server and verify over
`https://` — `report_data` then binds `sha256(nonce | tls-cert-fingerprint)`.

---

## 5 · Capture it

Record the `exodus verify` run for the demo. `asciinema rec` (terminal-native, crisp) or a
screen capture both work; keep the nonce visible so viewers can see it's fresh each run.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `DC1s_v3` greyed out / "not available" | Region out of SGX capacity → try another region, or request `DCSv3` quota. |
| `/dev/sgx_enclave` missing | SGX disabled in BIOS (bare metal), or a non-SGX VM size. |
| `aesmd` not running | `sudo systemctl enable --now aesmd`; needed for DCAP quoting. |
| Quote still `simulated` | The enclave can't reach the quoting service — confirm `sgx.remote_attestation = "dcap"` in the manifest and that `libsgx-dcap-ql` is installed. |
| `gramine-sgx: not found` | Re-run step [4] of the provisioning script (Gramine apt install). |

Honest-scope notes and the threat model the enclave does **not** change live in
[`docs/TEE.md`](TEE.md).
