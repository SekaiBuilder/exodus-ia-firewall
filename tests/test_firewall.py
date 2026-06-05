"""M2 — secret firewall tests (the invariants that make Exodus actually protect).

INV-1: no real SECRET value crosses egress.
INV-2: the vault (real values) is never serialized upstream.
INV-3: a pseudonymized value restored on the response path round-trips exactly.
Plus: stream-safe restoration across awkward chunk boundaries.
"""
import re

import httpx
import respx
from fastapi.testclient import TestClient

from exodus.proxy.server import create_app
from exodus.transform.pseudonymize import StreamRestorer, Vault


@respx.mock
def test_inv1_api_key_never_reaches_upstream():
    real = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    with TestClient(create_app()) as client:
        r = client.post(
            "/v1/messages",
            json={"model": "claude", "messages": [{"role": "user", "content": f"use key {real}"}]},
        )
    assert r.status_code == 200
    upstream_body = route.calls.last.request.content.decode("utf-8")
    assert real not in upstream_body                     # INV-1 / INV-2: real value never sent
    assert "⟪EXODUS:anthropic_key:" in upstream_body     # a placeholder went instead


@respx.mock
def test_inv3_secret_restored_for_the_client():
    real = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"  # matches openai_key (sk- + 20+)

    def echo(request):
        body = request.content.decode("utf-8")
        assert real not in body                          # upstream must not see the secret
        m = re.search(r"⟪EXODUS:[^⟫]+⟫", body)
        assert m, "expected a placeholder in the upstream body"
        return httpx.Response(200, json={"echoed": m.group(0)})

    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=echo)
    with TestClient(create_app()) as client:
        r = client.post(
            "/v1/messages",
            json={"model": "claude", "messages": [{"role": "user", "content": f"key={real}"}]},
        )
    assert r.status_code == 200
    assert real in r.text          # INV-3: the client sees the REAL value, restored
    assert "EXODUS:" not in r.text  # no placeholder leaks back to the client


def test_stream_restorer_survives_split_placeholders_and_multibyte():
    vault = Vault()
    token = vault.placeholder_for("super-secret-value", "api_key")
    data = ("before " + token + " after").encode("utf-8")

    restorer = StreamRestorer(vault)
    out = b""
    for i in range(0, len(data), 3):  # 3-byte chunks: splits the ⟪ (3-byte) char AND the token
        out += restorer.feed(data[i : i + 3])
    out += restorer.flush()
    assert out.decode("utf-8") == "before super-secret-value after"


@respx.mock
def test_multiple_secrets_in_nested_content():
    k1 = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAA1111"
    k2 = "AKIAIOSFODNN7EXAMPLE"  # aws_access_key
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    with TestClient(create_app()) as client:
        r = client.post(
            "/v1/messages",
            json={
                "model": "claude",
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": f"anthropic {k1}"}]},
                    {"role": "user", "content": f"aws {k2}"},
                ],
            },
        )
    assert r.status_code == 200
    sent = route.calls.last.request.content.decode("utf-8")
    assert k1 not in sent and k2 not in sent
    assert "⟪EXODUS:anthropic_key:" in sent and "⟪EXODUS:aws_access_key:" in sent


@respx.mock
def test_non_json_body_passes_through_untouched():
    route = respx.post("https://api.anthropic.com/v1/foo").mock(
        return_value=httpx.Response(200, content=b"pong")
    )
    with TestClient(create_app()) as client:
        r = client.post("/v1/foo", content=b"not json at all", headers={"content-type": "text/plain"})
    assert r.status_code == 200
    assert route.calls.last.request.content == b"not json at all"
    assert r.content == b"pong"
