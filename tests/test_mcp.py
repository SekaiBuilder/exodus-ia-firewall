"""MCP server tests — protocol handshake and tool dispatch over plain dicts."""
import json

from exodus.mcp_server import handle


def _call(name: str, arguments: dict, msg_id: int = 7) -> dict:
    resp = handle({
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    assert resp["id"] == msg_id
    return resp["result"]


def test_initialize_handshake():
    resp = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["serverInfo"]["name"] == "exodus"
    assert "tools" in resp["result"]["capabilities"]
    # The initialized notification must not produce a response.
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list():
    resp = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {"exodus_mask", "exodus_verify", "exodus_audit"}
    for tool in resp["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object"


def test_mask_tool_masks_a_secret():
    result = _call("exodus_mask", {"text": "key: sk-ant-api03-FAKEFAKEFAKEFAKEFAKE-FAKE"})
    payload = json.loads(result["content"][0]["text"])
    assert result["isError"] is False
    assert "sk-ant-" not in payload["masked_text"]
    assert payload["count"] >= 1


def test_mask_tool_passes_clean_text():
    result = _call("exodus_mask", {"text": "nothing sensitive here"})
    payload = json.loads(result["content"][0]["text"])
    assert payload["masked_text"] == "nothing sensitive here"
    assert payload["count"] == 0


def test_unknown_tool_is_an_error():
    resp = handle({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "nope", "arguments": {}},
    })
    assert resp["error"]["code"] == -32602


def test_unknown_method():
    resp = handle({"jsonrpc": "2.0", "id": 4, "method": "resources/list"})
    assert resp["error"]["code"] == -32601


def test_tool_failure_surfaces_as_tool_result():
    # exodus_verify against a closed port fails inside the tool, not the protocol.
    result = _call("exodus_verify", {"url": "http://127.0.0.1:1"})
    assert result["isError"] is True
