#!/usr/bin/env bash
# Provision a fresh Ubuntu 24.04 bare-metal SGX server for Exodus under gramine-sgx.
# Usage: bash provision-sgx-server.sh   (run as a sudo-capable user on the server)
set -euo pipefail

echo "== [1/7] Checking SGX hardware =="
if ! grep -qi sgx /proc/cpuinfo; then
  echo "WARNING: 'sgx' flag not in /proc/cpuinfo. SGX may be disabled in BIOS." >&2
fi

echo "== [2/7] Installing system packages =="
sudo apt-get update
sudo apt-get install -y curl gnupg ca-certificates python3 python3-venv python3-pip git cpuid

echo "== [3/7] Intel SGX/DCAP repo =="
. /etc/os-release
curl -fsSL https://download.01.org/intel-sgx/sgx_repo/ubuntu/intel-sgx-deb.key \
  | sudo gpg --dearmor -o /usr/share/keyrings/intel-sgx.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-sgx.gpg] https://download.01.org/intel-sgx/sgx_repo/ubuntu ${VERSION_CODENAME} main" \
  | sudo tee /etc/apt/sources.list.d/intel-sgx.list
sudo apt-get update
sudo apt-get install -y libsgx-dcap-ql libsgx-dcap-default-qpl libsgx-quote-ex sgx-aesm-service || true
sudo systemctl enable --now aesmd 2>/dev/null || true

echo "== [4/7] Gramine =="
# Same trusted=yes workaround as the Codespace: noble repo GPG signature fails.
echo "deb [arch=amd64 trusted=yes] https://packages.gramineproject.io/ ${VERSION_CODENAME} main" \
  | sudo tee /etc/apt/sources.list.d/gramine.list
sudo apt-get update
sudo apt-get install -y gramine

echo "== [5/7] Exodus clone + venv =="
cd "$HOME"
[ -d exodus-ia-firewall ] || git clone https://github.com/SekaiBuilder/exodus-ia-firewall.git
cd exodus-ia-firewall
PYBIN=$(readlink -f "$(command -v python3)")
python3 -m venv .venv
.venv/bin/pip install -q -e ".[dev]" 2>/dev/null || .venv/bin/pip install -q -e .

echo "== [6/7] Generating server manifest =="
REPO="$HOME/exodus-ia-firewall"
SITEPKG=$(.venv/bin/python -c "import site; print(site.getsitepackages()[0])")
cat > exodus.manifest.template.server <<EOF
loader.entrypoint = {uri = "file:{{ gramine.libos }}"}
libos.entrypoint = "${PYBIN}"
loader.log_level = "error"
loader.argv = ["${PYBIN}", "${REPO}/.venv/bin/exodus", "serve"]
loader.env.LD_LIBRARY_PATH = "/lib:{{ arch_libdir }}:/usr/lib/x86_64-linux-gnu"
loader.env.PYTHONPATH = "${REPO}/src:${SITEPKG}"
loader.env.HOME = "${HOME}"
loader.env.PYTHONDONTWRITEBYTECODE = "1"
sys.stack.size = "8M"
sys.brk.max_size = "512M"
sys.enable_sigterm_injection = true

fs.mounts = [
  { path = "/lib", uri = "file:{{ gramine.runtimedir() }}" },
  { path = "{{ arch_libdir }}", uri = "file:{{ arch_libdir }}" },
  { path = "/usr", uri = "file:/usr" },
  { path = "/bin", uri = "file:/bin" },
  { path = "/lib64", uri = "file:/lib64" },
  { path = "/etc", uri = "file:/etc" },
  { path = "/tmp", uri = "file:/tmp" },
  { path = "${HOME}", uri = "file:${HOME}" },
]

sgx.enclave_size = "2G"
sgx.max_threads = 32
sgx.remote_attestation = "dcap"

sgx.allowed_files = [
  "file:{{ gramine.runtimedir() }}/",
  "file:/usr/",
  "file:/bin/",
  "file:/lib/x86_64-linux-gnu/",
  "file:/lib64/",
  "file:/etc/",
  "file:/tmp/",
  "file:${HOME}/",
]
EOF

gramine-manifest -Darch_libdir=/lib/x86_64-linux-gnu \
  exodus.manifest.template.server exodus.manifest
[ -f "$HOME/.config/gramine/enclave-key.pem" ] || gramine-sgx-gen-private-key
gramine-sgx-sign --manifest exodus.manifest --output exodus.manifest.sgx

echo "== [7/7] Smoke test =="
ls -l /dev/sgx_enclave /dev/sgx_provision 2>/dev/null || echo "NOTE: /dev/sgx_* missing — check BIOS/driver."
echo "Run:  cd $REPO && gramine-sgx exodus   (serves on :8787)"
echo "Then from your Mac:  exodus verify https://SERVER:8787 --mrenclave <value printed by gramine-sgx-sign>"
echo "Provision complete."
