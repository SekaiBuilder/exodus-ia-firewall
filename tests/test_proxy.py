"""M1 — transparent proxy tests.

These mock the upstream Anthropic API with respx (no network) and assert that the
proxy relays requests faithfully, forwards auth headers, and streams SSE responses
back with the right content-type.
"""
import httpx
import respx
from fastapi.testclient import TestClient

from exodus.proxy.server import create_app


@respx.mock
def test_transparent_json_passthrough():
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    with TestClient(create_app()) as client:
        r = client.post(
            "/v1/messages",
            json={"model": "claude", "messages": []},
            headers={"x-api-key": "sk-test", "anthropic-version": "2023-06-01"},
        )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert route.called
    # The client's credentials are relayed upstream unchanged (M1 is transparent).
    sent = route.calls.last.request
    assert sent.headers.get("x-api-key") == "sk-test"
    assert sent.headers.get("anthropic-version") == "2023-06-01"


@respx.mock
def test_sse_stream_passthrough():
    sse = (
        b"event: message_start\ndata: {\"type\":\"message_start\"}\n\n"
        b"event: content_block_delta\ndata: {\"delta\":{\"text\":\"hi\"}}\n\n"
    )
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse)
    )
    with TestClient(create_app()) as client:
        r = client.post("/v1/messages", content=b"{}", headers={"content-type": "application/json"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert b"message_start" in r.content and b"content_block_delta" in r.content


def test_health():
    with TestClient(create_app()) as client:
        r = client.get("/_exodus/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and "stage" in r.json()
