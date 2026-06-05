"""Proof mode (EXODUS_NO_RESTORE): keep egress masking, skip response restoration.

Lets the user SEE, in their own client, the placeholder the cloud actually received —
visual proof that the real secret never left the machine. Off by default (restoration on).
"""
import re

import httpx
import respx
from fastapi.testclient import TestClient

from exodus.proxy.server import create_app

_SECRET = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA1111"


def _echo_placeholder(request):
    """Stand in for the cloud model quoting back whatever it received."""
    m = re.search(r"⟪EXODUS:[^⟫]+⟫", request.content.decode("utf-8"))
    return httpx.Response(200, json={"reply": m.group(0) if m else "<none>"})


@respx.mock
def test_no_restore_shows_placeholder(monkeypatch):
    # Proof mode ON: the client must see the centinela, NOT the restored secret.
    monkeypatch.setenv("EXODUS_NO_RESTORE", "on")
    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=_echo_placeholder)

    with TestClient(create_app()) as client:
        r = client.post(
            "/v1/messages",
            json={"model": "m", "messages": [{"role": "user", "content": f"repeat {_SECRET}"}]},
        )

    assert "⟪EXODUS:anthropic_key:" in r.text   # client sees what the cloud received
    assert _SECRET not in r.text                 # the real secret is NOT restored back


@respx.mock
def test_restore_is_on_by_default(monkeypatch):
    # Default (no flag): normal round-trip — the client gets the real value restored.
    monkeypatch.delenv("EXODUS_NO_RESTORE", raising=False)
    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=_echo_placeholder)

    with TestClient(create_app()) as client:
        r = client.post(
            "/v1/messages",
            json={"model": "m", "messages": [{"role": "user", "content": f"repeat {_SECRET}"}]},
        )

    assert _SECRET in r.text                      # normal mode restores the real value
    assert "⟪EXODUS:" not in r.text               # no placeholder leaks to the client
