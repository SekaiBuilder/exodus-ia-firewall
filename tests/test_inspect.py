"""Inspection log tests — captures BOTH sides of your own exchange (opt-in, debug).

Doubles as an end-to-end proof: what you wrote (real) vs. what was sent (masked) vs.
what Claude Code received (restored).
"""
import json
import re

import httpx
import respx
from fastapi.testclient import TestClient

from exodus.proxy.server import create_app

_SECRET = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA1111"


@respx.mock
def test_inspect_captures_both_sides(tmp_path, monkeypatch):
    monkeypatch.setenv("EXODUS_INSPECT", "on")
    monkeypatch.setenv("EXODUS_INSPECT_LOG", str(tmp_path / "i.jsonl"))

    def echo(request):
        m = re.search(r"⟪EXODUS:[^⟫]+⟫", request.content.decode("utf-8"))
        return httpx.Response(200, json={"reply": m.group(0) if m else ""})

    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=echo)

    with TestClient(create_app()) as client:
        client.post(
            "/v1/messages",
            json={"model": "m", "messages": [{"role": "user", "content": f"key {_SECRET}"}]},
        )

    rec = json.loads((tmp_path / "i.jsonl").read_text().strip())
    assert _SECRET in rec["you_wrote"]               # what you wrote (real)
    assert "⟪EXODUS:" in rec["sent_to_cloud"]        # what left (masked)
    assert _SECRET not in rec["sent_to_cloud"]       # real value never sent
    assert _SECRET in rec["claude_code_received"]    # restored for the client


def test_inspect_off_writes_nothing(tmp_path, monkeypatch):
    # Without EXODUS_INSPECT, no inspection file should be created.
    monkeypatch.delenv("EXODUS_INSPECT", raising=False)
    monkeypatch.setenv("EXODUS_INSPECT_LOG", str(tmp_path / "none.jsonl"))

    @respx.mock
    def run():
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        with TestClient(create_app()) as client:
            client.post("/v1/messages", json={"model": "m", "messages": [{"role": "user", "content": "hi"}]})

    run()
    assert not (tmp_path / "none.jsonl").exists()
