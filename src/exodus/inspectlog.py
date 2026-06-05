"""Local request/response inspection log: opt-in, for debugging only.

Unlike the audit trail (which records kinds, never values), this captures full
plaintext of both sides of your own exchange: what you wrote, what was sent to the
cloud (after masking), and what the client received (after restoration). Its only
purpose is to let you verify Exodus on your own traffic.

Rules:
  * OFF by default (enable with EXODUS_INSPECT=on).
  * The file contains secrets in clear text, so it is git-ignored; delete it when done.
  * Do NOT use this to capture anyone else's session without their consent. That would
    be surveillance, which Exodus is not for.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

DEFAULT_PATH = "inspect/exodus-inspect.jsonl"


def inspect_path() -> str:
    return os.getenv("EXODUS_INSPECT_LOG", DEFAULT_PATH)


def _txt(b) -> str:
    if isinstance(b, (bytes, bytearray)):
        return bytes(b).decode("utf-8", "replace")
    return str(b)


def record(request_id: str, you_wrote, sent_to_cloud, received_back, path: str | None = None) -> None:
    """Append one inspection record (full plaintext, both directions)."""
    path = path or inspect_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request_id": request_id,
        "you_wrote": _txt(you_wrote),
        "sent_to_cloud": _txt(sent_to_cloud),
        "claude_code_received": _txt(received_back),
    }
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
