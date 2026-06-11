# Demo: what the cloud actually sees when a request goes through Exodus.
# Regenerate from this directory:  vhs firewall.tape
# Needs: vhs (https://github.com/charmbracelet/vhs) and the repo venv installed (.venv).

Output ../assets/demo-firewall.gif

Set Shell "bash"
Set FontSize 15
Set Width 1280
Set Height 700
Set Padding 16
Set Theme "Catppuccin Mocha"
Set TypingSpeed 30ms

Hide
Type `export PATH="$PWD/../../.venv/bin:$PATH"`
Enter
Type "python3 -u echo_upstream.py > cloud.log 2>&1 &"
Enter
Type "EXODUS_UPSTREAM=http://127.0.0.1:9999 exodus serve >/dev/null 2>&1 &"
Enter
Sleep 3s
Type "clear"
Enter
Show

Type "# [1] A prompt that contains an API key and a credit card:"
Enter
Sleep 500ms
Type "cat request.json"
Enter
Sleep 3.5s
Type "# [2] Send it THROUGH Exodus (localhost:8787) instead of the provider API:"
Enter
Sleep 500ms
Type@20ms "curl -s localhost:8787/v1/messages -H 'content-type: application/json' -d @request.json | python3 -m json.tool"
Enter
Sleep 1s
Type "# ...the reply comes back with the original values restored - tools never notice."
Enter
Sleep 3.5s
Type "# [3] But this is what actually LEFT the machine:"
Enter
Sleep 500ms
Type "cat cloud.log"
Enter
Sleep 7s
