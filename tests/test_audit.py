"""M3 — audit trail tests: records WHAT was protected, never the values."""
import json

import httpx
import respx
from fastapi.testclient import TestClient

from exodus.audit import log as audit
from exodus.proxy.server import create_app

_SECRET = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA1111"


def test_write_and_summarize(tmp_path):
    p = tmp_path / "a.jsonl"
    audit.write(
        [
            audit.AuditRecord.now("req1", "anthropic_key", "pseudonymize"),
            audit.AuditRecord.now("req1", "email", "pseudonymize"),
        ],
        path=str(p),
    )
    s = audit.summarize(str(p))
    assert s["total"] == 2
    assert s["by_kind"]["anthropic_key"] == 1
    assert s["by_action"]["pseudonymize"] == 2


def test_audit_record_has_only_safe_fields(tmp_path):
    p = tmp_path / "a.jsonl"
    audit.write([audit.AuditRecord.now("req1", "anthropic_key", "block")], path=str(p))
    row = json.loads(p.read_text().strip())
    # A record carries a TYPE and metadata — never a value field.
    assert set(row) == {"ts", "request_id", "kind", "action"}


@respx.mock
def test_proxy_writes_audit_without_leaking_the_secret(tmp_path, monkeypatch):
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("EXODUS_AUDIT_LOG", str(log_path))
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    with TestClient(create_app()) as client:
        client.post(
            "/v1/messages",
            json={"model": "m", "messages": [{"role": "user", "content": f"key {_SECRET}"}]},
        )
    assert log_path.exists()
    s = audit.summarize(str(log_path))
    assert s["total"] >= 1
    assert s["by_kind"].get("anthropic_key") == 1
    # The audit file must NEVER contain the real secret.
    assert _SECRET not in log_path.read_text()
