# Demo: attestation handshake against a running proxy (simulated TEE on a dev box).
# Regenerate from this directory:  vhs verify.tape
# Needs: vhs (https://github.com/charmbracelet/vhs) and the repo venv installed (.venv).

Output ../assets/demo-verify.gif

Set Shell "bash"
Set FontSize 15
Set Width 1280
Set Height 280
Set Padding 16
Set Theme "Catppuccin Mocha"
Set TypingSpeed 30ms

Hide
Type `export PATH="$PWD/../../.venv/bin:$PATH"`
Enter
Type "exodus serve >/dev/null 2>&1 &"
Enter
Sleep 3s
Type "clear"
Enter
Show

Type "# Can this gateway be trusted? Fresh nonce -> attestation report -> verdict:"
Enter
Sleep 500ms
Type "exodus verify --url http://127.0.0.1:8787 --allow-simulated"
Enter
Sleep 7s
