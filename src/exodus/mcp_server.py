"""MCP server — Exodus tools for AI agents (Model Context Protocol).

Exposes the firewall to any MCP client (Claude Code, Claude Desktop, custom
agents) over the stdio transport: newline-delimited JSON-RPC 2.0.

Tools:
    exodus_mask    mask secrets/PII in a text before it travels anywhere
    exodus_verify  attestation handshake against a running Exodus proxy —
                   lets an agent check the privacy gateway *before* routing
                   secrets through it
    exodus_audit   summarize what the firewall has masked (never the values)

No third-party MCP SDK: the protocol surface needed here (initialize,
tools/list, tools/call, ping) is small enough to speak directly.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

PROTOCOL_VERSION = "2025-06-18"

_TOOLS = [
    {
        "name": "exodus_mask",
        "description": (
            "Mask secrets and PII in a text using the Exodus deterministic firewall. "
            "Returns the masked text and a summary of what was detected. Use before "
            "sending untrusted text to any external service."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to scan and mask."}},
            "required": ["text"],
        },
    },
    {
        "name": "exodus_verify",
        "description": (
            "Verify a running Exodus proxy's attestation (nonce freshness, report_data "
            "binding, TLS channel binding over https, MRENCLAVE pinning). Use to decide "
            "whether a privacy gateway can be trusted before routing secrets through it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Proxy base URL (http or https)."},
                "allow_simulated": {
                    "type": "boolean",
                    "description": "Accept simulated documents (development without SGX).",
                },
                "mrenclave": {"type": "string", "description": "Expected MRENCLAVE (hex)."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "exodus_audit",
        "description": "Summarize the Exodus audit trail: what was masked, by kind and action.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _tool_mask(args: dict) -> dict:
    from exodus.transform.pipeline import mask_text

    masked, _vault, applied = mask_text(str(args.get("text", "")))
    return {
        "masked_text": masked,
        "detections": dict(Counter(f"{kind}:{action}" for kind, action in applied)),
        "count": len(applied),
    }


def _tool_verify(args: dict) -> dict:
    from exodus.verify import verify_url

    v = verify_url(
        str(args["url"]),
        expected_mrenclave=args.get("mrenclave"),
        allow_simulated=bool(args.get("allow_simulated", False)),
    )
    return {
        "trusted": v.trusted,
        "tee": v.tee,
        "checks": v.checks,
        "failures": v.failures,
        "mr_enclave": v.mr_enclave,
        "mr_signer": v.mr_signer,
    }


def _tool_audit(_args: dict) -> dict:
    from exodus.audit import log as audit

    return audit.summarize(None)


_HANDLERS = {
    "exodus_mask": _tool_mask,
    "exodus_verify": _tool_verify,
    "exodus_audit": _tool_audit,
}


def handle(msg: dict) -> dict | None:
    """Process one JSON-RPC message; return the response (None for notifications)."""
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        return _result(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "exodus", "version": "0.0.1"},
        })
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _result(msg_id, {})
    if method == "tools/list":
        return _result(msg_id, {"tools": _TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        handler = _HANDLERS.get(name)
        if handler is None:
            return _error(msg_id, -32602, f"unknown tool: {name}")
        try:
            payload = handler(params.get("arguments") or {})
        except Exception as exc:  # surface tool failures as tool results, per MCP
            return _result(msg_id, {
                "content": [{"type": "text", "text": f"error: {exc}"}],
                "isError": True,
            })
        return _result(msg_id, {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "isError": False,
        })
    if msg_id is None:
        return None  # unknown notification — ignore
    return _error(msg_id, -32601, f"method not found: {method}")


def _result(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def main() -> int:
    """Serve MCP over stdio until EOF."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0
