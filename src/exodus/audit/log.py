"""Transparent audit trail.

Records what Exodus did (kind + action + when), never the real values. The audit
file is safe to read and to share: it proves the firewall is working without
leaking anything it protected. One JSON object per line (JSONL).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

DEFAULT_PATH = "audit/exodus.jsonl"


def audit_path() -> str:
    return os.getenv("EXODUS_AUDIT_LOG", DEFAULT_PATH)


@dataclass
class AuditRecord:
    ts: str           # ISO-8601 UTC
    request_id: str   # local correlation id for one request
    kind: str         # e.g. "anthropic_key"  (a TYPE, never a value)
    action: str       # "pseudonymize" | "block"

    @classmethod
    def now(cls, request_id: str, kind: str, action: str) -> "AuditRecord":
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return cls(ts=ts, request_id=request_id, kind=kind, action=action)


def write(records, path: str | None = None) -> None:
    """Append audit records as JSON lines. By construction, no real value is written."""
    records = list(records)
    if not records:
        return
    path = path or audit_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")


def summarize(path: str | None = None) -> dict:
    """Read the audit log and return totals by kind/action plus the last few rows."""
    path = path or audit_path()
    summary = {"path": path, "total": 0, "by_kind": {}, "by_action": {}, "recent": []}
    if not os.path.exists(path):
        return summary

    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append(row)
            k, a = row.get("kind", "?"), row.get("action", "?")
            summary["by_kind"][k] = summary["by_kind"].get(k, 0) + 1
            summary["by_action"][a] = summary["by_action"].get(a, 0) + 1

    summary["total"] = len(rows)
    summary["recent"] = rows[-10:]
    return summary
