#!/usr/bin/env bash
# Exodus status line for Claude Code.
# Shows "🛡 WITH EXODUS" in Claude Code's bottom bar when the session is routed
# through the local Exodus proxy (i.e. ANTHROPIC_BASE_URL points at localhost).
#
# Enable it by adding this to ~/.claude/settings.json:
#   "statusLine": {
#     "type": "command",
#     "command": "/Users/francesco_mac/proyect ghithub/proyecto-exodus/scripts/exodus-statusline.sh"
#   }
#
# Claude Code pipes a session JSON object on stdin; we don't need it here.

cat >/dev/null 2>&1   # consume stdin

label="Claude v2.1.161"
base="${ANTHROPIC_BASE_URL:-}"

if [[ -n "$base" && ( "$base" == *"127.0.0.1"* || "$base" == *"localhost"* ) ]]; then
  # Bright green shield — you are protected.
  printf '\033[92;1m🛡  %s · WITH EXODUS\033[0m' "$label"
else
  # Dim — talking to Anthropic directly.
  printf '\033[90m○ %s · direct (no Exodus)\033[0m' "$label"
fi
